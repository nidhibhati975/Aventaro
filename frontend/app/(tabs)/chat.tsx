import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Image,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { Audio } from 'expo-av';
import api from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';

interface Conversation {
  id: string;
  type: string;
  name?: string;
  image?: string;
  participants_info: { id: string; name: string; image?: string }[];
  last_message_preview?: string;
  last_message_at?: string;
  unread_count: number;
}

interface Message {
  id: string;
  sender_id: string;
  message_type: string;
  content: string;
  media_url?: string;
  status: string;
  read_by: string[];
  created_at: string;
}

export default function Chat() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConv, setSelectedConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [isTyping, setIsTyping] = useState<{[key: string]: boolean}>({});
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const flatListRef = useRef<FlatList>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (selectedConv) {
      loadMessages(selectedConv.id);
      markPresenceOnline();
    }
  }, [selectedConv]);

  const loadConversations = async () => {
    try {
      setLoading(true);
      const response = await api.get('/chat/conversations');
      setConversations(response.data.conversations || []);
    } catch (error) {
      console.error('Error loading conversations:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (conversationId: string) => {
    try {
      const response = await api.get(`/chat/messages/${conversationId}`);
      setMessages(response.data.messages || []);
    } catch (error) {
      console.error('Error loading messages:', error);
    }
  };

  const markPresenceOnline = async () => {
    try {
      await api.post('/chat/presence', { is_online: true });
    } catch (error) {}
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedConv) return;
    
    setSending(true);
    try {
      await api.post('/chat/message/send', null, {
        params: {
          conversation_id: selectedConv.id,
          content: newMessage.trim(),
          message_type: 'text'
        }
      });
      setNewMessage('');
      loadMessages(selectedConv.id);
    } catch (error) {
      Alert.alert('Error', 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const sendTypingIndicator = useCallback(async (typing: boolean) => {
    if (!selectedConv) return;
    try {
      await api.post('/chat/typing', null, {
        params: { conversation_id: selectedConv.id, is_typing: typing }
      });
    } catch (error) {}
  }, [selectedConv]);

  const handleTextChange = (text: string) => {
    setNewMessage(text);
    
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    
    if (text.length > 0) {
      sendTypingIndicator(true);
      typingTimeoutRef.current = setTimeout(() => {
        sendTypingIndicator(false);
      }, 3000);
    } else {
      sendTypingIndicator(false);
    }
  };

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.All,
      quality: 0.8,
    });
    
    if (!result.canceled && result.assets[0] && selectedConv) {
      const formData = new FormData();
      formData.append('file', {
        uri: result.assets[0].uri,
        type: result.assets[0].type === 'video' ? 'video/mp4' : 'image/jpeg',
        name: 'media.jpg',
      } as any);
      
      try {
        await api.post(
          `/chat/message/media?conversation_id=${selectedConv.id}&message_type=${result.assets[0].type === 'video' ? 'video' : 'image'}`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        loadMessages(selectedConv.id);
      } catch (error) {
        Alert.alert('Error', 'Failed to send media');
      }
    }
  };

  const pickDocument = async () => {
    const result = await DocumentPicker.getDocumentAsync({});
    
    if (result.assets && result.assets[0] && selectedConv) {
      const formData = new FormData();
      formData.append('file', {
        uri: result.assets[0].uri,
        type: result.assets[0].mimeType || 'application/octet-stream',
        name: result.assets[0].name,
      } as any);
      
      try {
        await api.post(
          `/chat/message/media?conversation_id=${selectedConv.id}&message_type=document`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        loadMessages(selectedConv.id);
      } catch (error) {
        Alert.alert('Error', 'Failed to send document');
      }
    }
  };

  const startRecording = async () => {
    try {
      await Audio.requestPermissionsAsync();
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
      
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      setRecording(recording);
      setIsRecording(true);
    } catch (error) {
      Alert.alert('Error', 'Failed to start recording');
    }
  };

  const stopRecording = async () => {
    if (!recording || !selectedConv) return;
    
    setIsRecording(false);
    await recording.stopAndUnloadAsync();
    const uri = recording.getURI();
    setRecording(null);
    
    if (uri) {
      const formData = new FormData();
      formData.append('file', {
        uri,
        type: 'audio/m4a',
        name: 'voice_note.m4a',
      } as any);
      
      try {
        await api.post(
          `/chat/message/media?conversation_id=${selectedConv.id}&message_type=voice_note`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        loadMessages(selectedConv.id);
      } catch (error) {
        Alert.alert('Error', 'Failed to send voice note');
      }
    }
  };

  const renderConversation = ({ item }: { item: Conversation }) => {
    const otherParticipant = item.participants_info?.[0];
    const displayName = item.name || otherParticipant?.name || 'Unknown';
    const displayImage = item.image || otherParticipant?.image;
    
    return (
      <TouchableOpacity
        style={styles.convItem}
        onPress={() => setSelectedConv(item)}
      >
        <View style={styles.avatar}>
          {displayImage ? (
            <Image source={{ uri: displayImage }} style={styles.avatarImage} />
          ) : (
            <Ionicons name="person" size={24} color="#9CA3AF" />
          )}
        </View>
        <View style={styles.convInfo}>
          <Text style={styles.convName}>{displayName}</Text>
          <Text style={styles.convPreview} numberOfLines={1}>
            {item.last_message_preview || 'No messages yet'}
          </Text>
        </View>
        {item.unread_count > 0 && (
          <View style={styles.unreadBadge}>
            <Text style={styles.unreadText}>{item.unread_count}</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  const renderMessage = ({ item }: { item: Message }) => {
    const isMe = item.sender_id === user?.id;
    
    return (
      <View style={[styles.messageContainer, isMe ? styles.myMessage : styles.theirMessage]}>
        <View style={[styles.messageBubble, isMe ? styles.myBubble : styles.theirBubble]}>
          {item.message_type === 'text' && (
            <Text style={[styles.messageText, isMe && styles.myMessageText]}>
              {item.content}
            </Text>
          )}
          {item.message_type === 'image' && item.media_url && (
            <Image source={{ uri: item.media_url }} style={styles.mediaImage} />
          )}
          {item.message_type === 'voice_note' && (
            <View style={styles.voiceNote}>
              <Ionicons name="mic" size={20} color={isMe ? '#FFFFFF' : '#8B5CF6'} />
              <Text style={[styles.voiceLabel, isMe && { color: '#FFFFFF' }]}>Voice message</Text>
            </View>
          )}
          <View style={styles.messageFooter}>
            <Text style={[styles.messageTime, isMe && styles.myMessageTime]}>
              {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </Text>
            {isMe && (
              <Ionicons
                name={item.status === 'read' ? 'checkmark-done' : item.status === 'delivered' ? 'checkmark-done' : 'checkmark'}
                size={14}
                color={item.status === 'read' ? '#60A5FA' : '#FFFFFF80'}
                style={{ marginLeft: 4 }}
              />
            )}
          </View>
        </View>
      </View>
    );
  };

  if (selectedConv) {
    const otherParticipant = selectedConv.participants_info?.[0];
    const displayName = selectedConv.name || otherParticipant?.name || 'Chat';
    
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        {/* Chat Header */}
        <View style={styles.chatHeader}>
          <TouchableOpacity onPress={() => setSelectedConv(null)}>
            <Ionicons name="arrow-back" size={24} color="#1F2937" />
          </TouchableOpacity>
          <View style={styles.chatHeaderInfo}>
            <Text style={styles.chatHeaderName}>{displayName}</Text>
            {isTyping[selectedConv.id] && (
              <Text style={styles.typingText}>typing...</Text>
            )}
          </View>
          <TouchableOpacity>
            <Ionicons name="call" size={24} color="#8B5CF6" />
          </TouchableOpacity>
        </View>

        {/* Messages */}
        <FlatList
          ref={flatListRef}
          data={messages}
          renderItem={renderMessage}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.messagesList}
          inverted={false}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
        />

        {/* Input */}
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={0}
        >
          <View style={styles.inputContainer}>
            <TouchableOpacity style={styles.attachButton} onPress={pickImage}>
              <Ionicons name="image" size={24} color="#6B7280" />
            </TouchableOpacity>
            <TouchableOpacity style={styles.attachButton} onPress={pickDocument}>
              <Ionicons name="attach" size={24} color="#6B7280" />
            </TouchableOpacity>
            
            <TextInput
              style={styles.input}
              value={newMessage}
              onChangeText={handleTextChange}
              placeholder="Type a message..."
              placeholderTextColor="#9CA3AF"
              multiline
            />
            
            {newMessage.trim() ? (
              <TouchableOpacity
                style={styles.sendButton}
                onPress={sendMessage}
                disabled={sending}
              >
                {sending ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Ionicons name="send" size={20} color="#FFFFFF" />
                )}
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={[styles.sendButton, isRecording && styles.recordingButton]}
                onPressIn={startRecording}
                onPressOut={stopRecording}
              >
                <Ionicons name="mic" size={20} color="#FFFFFF" />
              </TouchableOpacity>
            )}
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Messages</Text>
        <TouchableOpacity>
          <Ionicons name="create-outline" size={24} color="#8B5CF6" />
        </TouchableOpacity>
      </View>

      {loading ? (
        <ActivityIndicator size="large" color="#8B5CF6" style={{ marginTop: 50 }} />
      ) : conversations.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="chatbubbles-outline" size={64} color="#D1D5DB" />
          <Text style={styles.emptyText}>No conversations yet</Text>
          <Text style={styles.emptySubtext}>Match with people to start chatting</Text>
        </View>
      ) : (
        <FlatList
          data={conversations}
          renderItem={renderConversation}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  headerTitle: { fontSize: 24, fontWeight: '700', color: '#1F2937' },
  list: { padding: 16 },
  convItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  avatar: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  avatarImage: { width: 50, height: 50, borderRadius: 25 },
  convInfo: { flex: 1 },
  convName: { fontSize: 16, fontWeight: '600', color: '#1F2937' },
  convPreview: { fontSize: 14, color: '#6B7280', marginTop: 2 },
  unreadBadge: {
    backgroundColor: '#8B5CF6',
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 6,
  },
  unreadText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyText: { fontSize: 18, fontWeight: '600', color: '#6B7280', marginTop: 16 },
  emptySubtext: { fontSize: 14, color: '#9CA3AF', marginTop: 4 },
  chatHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  chatHeaderInfo: { flex: 1, marginLeft: 12 },
  chatHeaderName: { fontSize: 18, fontWeight: '600', color: '#1F2937' },
  typingText: { fontSize: 12, color: '#10B981', fontStyle: 'italic' },
  messagesList: { padding: 16, paddingBottom: 8 },
  messageContainer: { marginBottom: 8 },
  myMessage: { alignItems: 'flex-end' },
  theirMessage: { alignItems: 'flex-start' },
  messageBubble: {
    maxWidth: '80%',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 16,
  },
  myBubble: {
    backgroundColor: '#8B5CF6',
    borderBottomRightRadius: 4,
  },
  theirBubble: {
    backgroundColor: '#F3F4F6',
    borderBottomLeftRadius: 4,
  },
  messageText: { fontSize: 15, color: '#1F2937', lineHeight: 20 },
  myMessageText: { color: '#FFFFFF' },
  messageFooter: { flexDirection: 'row', alignItems: 'center', marginTop: 4 },
  messageTime: { fontSize: 11, color: '#6B7280' },
  myMessageTime: { color: '#FFFFFF80' },
  mediaImage: { width: 200, height: 200, borderRadius: 12 },
  voiceNote: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  voiceLabel: { fontSize: 14, color: '#8B5CF6' },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    backgroundColor: '#FFFFFF',
  },
  attachButton: { padding: 8 },
  input: {
    flex: 1,
    backgroundColor: '#F3F4F6',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    marginHorizontal: 8,
    fontSize: 15,
    maxHeight: 100,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#8B5CF6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  recordingButton: { backgroundColor: '#EF4444' },
});
