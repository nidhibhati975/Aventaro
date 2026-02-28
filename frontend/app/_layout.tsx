import React, { useEffect, useState } from 'react';
import { Stack } from 'expo-router';
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import FloatingChatButton from '../components/FloatingChatButton';
import { View } from 'react-native';
import api from '../services/api';

function RootLayoutNav() {
  const { user } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  
  useEffect(() => {
    if (user) {
      fetchUnreadCount();
      const interval = setInterval(fetchUnreadCount, 30000);
      return () => clearInterval(interval);
    }
  }, [user]);
  
  const fetchUnreadCount = async () => {
    try {
      const response = await api.get('/chat/notifications');
      setUnreadCount(response.data.unread || 0);
    } catch (error) {
      // Silently fail
    }
  };
  
  return (
    <View style={{ flex: 1 }}>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(tabs)" />
      </Stack>
      {user && <FloatingChatButton unreadCount={unreadCount} />}
    </View>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootLayoutNav />
    </AuthProvider>
  );
}
