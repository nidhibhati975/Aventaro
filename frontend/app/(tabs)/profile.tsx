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
import { useRouter } from 'expo-router';
import { useAuth } from '../../contexts/AuthContext';
import api from '../../services/api';

export default function Profile() {
  const { user, signOut } = useAuth();
  const [userData, setUserData] = useState<any>(null);
  const [walletBalance, setWalletBalance] = useState(0);
  const [rewardPoints, setRewardPoints] = useState(0);
  const [referralCode, setReferralCode] = useState('');
  const [successfulReferrals, setSuccessfulReferrals] = useState(0);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    loadUserData();
  }, []);

  const loadUserData = async () => {
    setLoading(true);
    try {
      const [userResponse, walletResponse, referralResponse] = await Promise.all([
        api.get('/api/auth/me'),
        api.get('/api/wallet/balance'),
        api.get('/api/referral/code'),
      ]);

      setUserData(userResponse.data);
      setWalletBalance(walletResponse.data.balance);
      setRewardPoints(walletResponse.data.reward_points);
      setReferralCode(referralResponse.data.referral_code);
      setSuccessfulReferrals(referralResponse.data.successful_referrals);
    } catch (error) {
      console.error('Error loading user data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = () => {
    Alert.alert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Sign Out',
          style: 'destructive',
          onPress: async () => {
            await signOut();
            router.replace('/(auth)/splash');
          },
        },
      ]
    );
  };

  const handleTopUpWallet = () => {
    Alert.alert('Wallet Top-Up', 'Wallet top-up feature coming soon!');
  };

  const handleShareReferral = () => {
    Alert.alert('Referral Code', `Your referral code: ${referralCode}\n\nShare this with friends!`);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color="#8B5CF6" style={{ marginTop: 100 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.notificationIcon}>
            <Ionicons name="shield-checkmark" size={24} color="#1F2937" />
          </TouchableOpacity>
        </View>

        {/* Profile Section */}
        <View style={styles.profileSection}>
          <View style={styles.avatarContainer}>
            {userData?.profile_image ? (
              <Image source={{ uri: userData.profile_image }} style={styles.avatar} />
            ) : (
              <View style={[styles.avatar, styles.avatarPlaceholder]}>
                <Ionicons name="person" size={48} color="#D1D5DB" />
              </View>
            )}
            <TouchableOpacity style={styles.editAvatarButton}>
              <Ionicons name="camera" size={16} color="#FFFFFF" />
            </TouchableOpacity>
          </View>

          <Text style={styles.name}>{userData?.full_name}</Text>
          <Text style={styles.email}>{userData?.email}</Text>

          {userData?.bio && <Text style={styles.bio}>{userData.bio}</Text>}

          <View style={styles.statsContainer}>
            <View style={styles.statItem}>
              <Ionicons name="location" size={16} color="#8B5CF6" />
              <Text style={styles.statText}>{userData?.city}</Text>
            </View>
            <View style={styles.statItem}>
              <Ionicons name="heart" size={16} color="#8B5CF6" />
              <Text style={styles.statText}>{userData?.relationship_status}</Text>
            </View>
          </View>

          {userData?.interests && userData.interests.length > 0 && (
            <View style={styles.interestsContainer}>
              {userData.interests.map((interest: string, index: number) => (
                <View key={index} style={styles.interestTag}>
                  <Text style={styles.interestText}>{interest}</Text>
                </View>
              ))}
            </View>
          )}
        </View>

        {/* Wallet Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Wallet & Rewards</Text>
          
          <View style={styles.walletCard}>
            <View style={styles.walletRow}>
              <View style={styles.walletItem}>
                <Text style={styles.walletLabel}>Wallet Balance</Text>
                <Text style={styles.walletValue}>₹{(walletBalance / 100).toFixed(2)}</Text>
              </View>
              <View style={styles.walletItem}>
                <Text style={styles.walletLabel}>Reward Points</Text>
                <Text style={styles.walletValue}>{rewardPoints}</Text>
              </View>
            </View>
            <TouchableOpacity style={styles.topUpButton} onPress={handleTopUpWallet}>
              <Ionicons name="add-circle" size={20} color="#FFFFFF" />
              <Text style={styles.topUpButtonText}>Top Up Wallet</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Referral Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Referral Program</Text>
          
          <View style={styles.referralCard}>
            <View style={styles.referralHeader}>
              <Ionicons name="gift" size={32} color="#D97706" />
              <View style={styles.referralInfo}>
                <Text style={styles.referralTitle}>Refer & Earn</Text>
                <Text style={styles.referralSubtitle}>
                  {successfulReferrals}/3 referrals for free boost
                </Text>
              </View>
            </View>

            <View style={styles.referralCodeContainer}>
              <View style={styles.referralCodeBox}>
                <Text style={styles.referralCodeLabel}>Your Code</Text>
                <Text style={styles.referralCodeText}>{referralCode}</Text>
              </View>
              <TouchableOpacity style={styles.shareButton} onPress={handleShareReferral}>
                <Ionicons name="share-social" size={20} color="#FFFFFF" />
              </TouchableOpacity>
            </View>

            <View style={styles.referralProgress}>
              <View style={styles.progressBar}>
                <View
                  style={[
                    styles.progressFill,
                    { width: `${(successfulReferrals / 3) * 100}%` },
                  ]}
                />
              </View>
              <Text style={styles.progressText}>
                {3 - successfulReferrals} more referrals to unlock free boost!
              </Text>
            </View>
          </View>
        </View>

        {/* Menu Options */}
        <View style={styles.section}>
          <TouchableOpacity style={styles.menuItem}>
            <View style={styles.menuLeft}>
              <Ionicons name="person-circle-outline" size={24} color="#6B7280" />
              <Text style={styles.menuText}>Edit Profile</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <View style={styles.menuLeft}>
              <Ionicons name="settings-outline" size={24} color="#6B7280" />
              <Text style={styles.menuText}>Settings</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <View style={styles.menuLeft}>
              <Ionicons name="help-circle-outline" size={24} color="#6B7280" />
              <Text style={styles.menuText}>Help & Support</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem} onPress={handleSignOut}>
            <View style={styles.menuLeft}>
              <Ionicons name="log-out-outline" size={24} color="#EF4444" />
              <Text style={[styles.menuText, { color: '#EF4444' }]}>Sign Out</Text>
            </View>
          </TouchableOpacity>
        </View>

        <Text style={styles.version}>Aventaro v1.0.0</Text>
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
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingHorizontal: 24,
    paddingVertical: 16,
  },
  notificationIcon: {
    padding: 4,
  },
  profileSection: {
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingBottom: 24,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  avatarContainer: {
    position: 'relative',
    marginBottom: 16,
  },
  avatar: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#F3F4F6',
  },
  avatarPlaceholder: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  editAvatarButton: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#8B5CF6',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: '#FFFFFF',
  },
  name: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: 4,
  },
  email: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 12,
  },
  bio: {
    fontSize: 14,
    color: '#374151',
    textAlign: 'center',
    marginBottom: 16,
    lineHeight: 20,
  },
  statsContainer: {
    flexDirection: 'row',
    gap: 24,
    marginBottom: 16,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  statText: {
    fontSize: 14,
    color: '#6B7280',
  },
  interestsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    justifyContent: 'center',
  },
  interestTag: {
    backgroundColor: '#EDE9FE',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  interestText: {
    fontSize: 12,
    color: '#7C3AED',
    fontWeight: '500',
  },
  section: {
    paddingHorizontal: 24,
    paddingVertical: 24,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: 16,
  },
  walletCard: {
    backgroundColor: '#F9FAFB',
    padding: 20,
    borderRadius: 12,
    gap: 16,
  },
  walletRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  walletItem: {
    flex: 1,
  },
  walletLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 4,
  },
  walletValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  topUpButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#8B5CF6',
    paddingVertical: 12,
    borderRadius: 8,
    gap: 8,
  },
  topUpButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  referralCard: {
    backgroundColor: '#FFFBEB',
    padding: 20,
    borderRadius: 12,
    gap: 16,
  },
  referralHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  referralInfo: {
    flex: 1,
  },
  referralTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: 2,
  },
  referralSubtitle: {
    fontSize: 13,
    color: '#6B7280',
  },
  referralCodeContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  referralCodeBox: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    padding: 12,
    borderRadius: 8,
  },
  referralCodeLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 4,
  },
  referralCodeText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#D97706',
  },
  shareButton: {
    width: 48,
    height: 48,
    borderRadius: 8,
    backgroundColor: '#D97706',
    justifyContent: 'center',
    alignItems: 'center',
  },
  referralProgress: {
    gap: 8,
  },
  progressBar: {
    height: 8,
    backgroundColor: '#FEF3C7',
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#D97706',
  },
  progressText: {
    fontSize: 12,
    color: '#92400E',
    textAlign: 'center',
  },
  menuItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 16,
  },
  menuLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  menuText: {
    fontSize: 16,
    color: '#374151',
  },
  version: {
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'center',
    paddingVertical: 24,
  },
});