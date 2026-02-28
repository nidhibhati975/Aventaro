import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Image,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

export default function Matches() {
  const [activeTab, setActiveTab] = useState<'friend' | 'trip'>('friend');
  const [friendRequests, setFriendRequests] = useState<any[]>([]);
  const [tripRequests, setTripRequests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'friend') {
        const response = await api.get('/users/friend-requests');
        setFriendRequests(response.data);
      } else {
        // Load trip requests (trips where current user is creator)
        const myTrips = await api.get('/trips/my-trips');
        const created = myTrips.data.created || [];
        const allRequests: any[] = [];
        
        for (const trip of created) {
          if (trip.pending_requests && trip.pending_requests.length > 0) {
            const requests = await api.get(`/trips/${trip.id}/requests`);
            allRequests.push(...requests.data.map((user: any) => ({ ...user, trip })));
          }
        }
        setTripRequests(allRequests);
      }
    } catch (error) {
      console.error('Error loading requests:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAcceptFriend = async (requestId: string) => {
    try {
      await api.post(`/users/friend-request/${requestId}/accept`);
      Alert.alert('Success', 'Friend request accepted!');
      loadData();
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to accept request');
    }
  };

  const handleApproveTripRequest = async (tripId: string, userId: string) => {
    try {
      await api.post(`/trips/${tripId}/approve/${userId}`);
      Alert.alert('Success', 'Trip request approved!');
      loadData();
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to approve request');
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Matches</Text>
      </View>

      <View style={styles.tabsContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'friend' && styles.tabActive]}
          onPress={() => setActiveTab('friend')}
        >
          <Text style={[styles.tabText, activeTab === 'friend' && styles.tabTextActive]}>
            Friend Requests
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'trip' && styles.tabActive]}
          onPress={() => setActiveTab('trip')}
        >
          <Text style={[styles.tabText, activeTab === 'trip' && styles.tabTextActive]}>
            Trip Join Requests
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content}>
        {loading ? (
          <ActivityIndicator size="large" color="#8B5CF6" style={{ marginTop: 32 }} />
        ) : activeTab === 'friend' ? (
          friendRequests.length > 0 ? (
            friendRequests.map((request) => (
              <View key={request.id} style={styles.card}>
                <View style={styles.cardLeft}>
                  {request.user?.profile_image ? (
                    <Image source={{ uri: request.user.profile_image }} style={styles.avatar} />
                  ) : (
                    <View style={[styles.avatar, styles.avatarPlaceholder]}>
                      <Ionicons name="person" size={24} color="#D1D5DB" />
                    </View>
                  )}
                  <View style={styles.cardInfo}>
                    <Text style={styles.cardName}>{request.user?.full_name}</Text>
                    <Text style={styles.cardDetail}>{request.user?.city}</Text>
                  </View>
                </View>
                <TouchableOpacity
                  style={styles.acceptButton}
                  onPress={() => handleAcceptFriend(request.id)}
                >
                  <Ionicons name="checkmark" size={20} color="#FFFFFF" />
                </TouchableOpacity>
              </View>
            ))
          ) : (
            <View style={styles.emptyState}>
              <Ionicons name="people-outline" size={64} color="#D1D5DB" />
              <Text style={styles.emptyText}>No friend requests</Text>
            </View>
          )
        ) : tripRequests.length > 0 ? (
          tripRequests.map((request, index) => (
            <View key={index} style={styles.card}>
              <View style={styles.cardLeft}>
                {request.profile_image ? (
                  <Image source={{ uri: request.profile_image }} style={styles.avatar} />
                ) : (
                  <View style={[styles.avatar, styles.avatarPlaceholder]}>
                    <Ionicons name="person" size={24} color="#D1D5DB" />
                  </View>
                )}
                <View style={styles.cardInfo}>
                  <Text style={styles.cardName}>{request.full_name}</Text>
                  <Text style={styles.cardDetail}>Trip: {request.trip?.destination}</Text>
                  <Text style={styles.cardDetailSmall}>{request.city}</Text>
                </View>
              </View>
              <TouchableOpacity
                style={styles.acceptButton}
                onPress={() => handleApproveTripRequest(request.trip.id, request.id)}
              >
                <Ionicons name="checkmark" size={20} color="#FFFFFF" />
              </TouchableOpacity>
            </View>
          ))
        ) : (
          <View style={styles.emptyState}>
            <Ionicons name="airplane-outline" size={64} color="#D1D5DB" />
            <Text style={styles.emptyText}>No trip join requests</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  header: {
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  tabsContainer: {
    flexDirection: 'row',
    paddingHorizontal: 24,
    paddingTop: 16,
    gap: 8,
  },
  tab: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: 8,
    backgroundColor: '#F3F4F6',
  },
  tabActive: {
    backgroundColor: '#8B5CF6',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
  },
  tabTextActive: {
    color: '#FFFFFF',
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 16,
  },
  card: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  cardLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#F3F4F6',
  },
  avatarPlaceholder: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  cardInfo: {
    marginLeft: 12,
    flex: 1,
  },
  cardName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 4,
  },
  cardDetail: {
    fontSize: 14,
    color: '#6B7280',
  },
  cardDetailSmall: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  acceptButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#10B981',
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 16,
    color: '#9CA3AF',
    marginTop: 16,
  },
});