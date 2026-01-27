import React, { createContext, useState, useContext, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';

const API_URL = `${process.env.EXPO_PUBLIC_BACKEND_URL || 'http://localhost'}/api`;

interface User {
  id: string;
  full_name: string;
  email: string;
  profile_image?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  signIn: (login: string, password: string) => Promise<void>;
  signUp: (userData: any) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  signIn: async () => {},
  signUp: async () => {},
  signOut: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStoredAuth();
  }, []);

  const loadStoredAuth = async () => {
    try {
      const storedToken = await AsyncStorage.getItem('auth_token');
      const storedUser = await AsyncStorage.getItem('user');

      if (storedToken && storedUser) {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      }
    } catch (error) {
      console.error('Error loading auth:', error);
    } finally {
      setLoading(false);
    }
  };

  const signIn = async (login: string, password: string) => {
    try {
      console.log('Signing in to:', `${API_URL}/auth/signin`);
      const response = await axios.post(`${API_URL}/auth/signin`, { login, password });
      const { token: newToken, user: newUser } = response.data;

      console.log('Sign in successful, storing token...');
      await AsyncStorage.setItem('auth_token', newToken);
      await AsyncStorage.setItem('user', JSON.stringify(newUser));

      setToken(newToken);
      setUser(newUser);
      console.log('User set:', newUser);
    } catch (error: any) {
      console.error('Sign in error:', error);
      throw new Error(error.response?.data?.detail || 'Sign in failed');
    }
  };

  const signUp = async (userData: any) => {
    try {
      console.log('Signing up to:', `${API_URL}/auth/signup`);
      const response = await axios.post(`${API_URL}/auth/signup`, userData);
      const { token: newToken, user: newUser } = response.data;

      console.log('Sign up successful, storing token...');
      await AsyncStorage.setItem('auth_token', newToken);
      await AsyncStorage.setItem('user', JSON.stringify(newUser));

      setToken(newToken);
      setUser(newUser);
      console.log('User set:', newUser);
    } catch (error: any) {
      console.error('Sign up error:', error);
      throw new Error(error.response?.data?.detail || 'Sign up failed');
    }
  };

  const signOut = async () => {
    await AsyncStorage.removeItem('auth_token');
    await AsyncStorage.removeItem('user');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
};