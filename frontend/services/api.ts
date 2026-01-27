import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_URL = `${process.env.EXPO_PUBLIC_BACKEND_URL || 'http://localhost'}/api`;

const api = axios.create({
  baseURL: API_URL,
  timeout: 10000,
});

// Add auth token to requests
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;