import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

interface Commission {
  id: string;
  booking_id: string;
  commission_amount: number;
  status: string;
  created_at: string;
}

export default function AffiliateDashboard() {
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState<any>(null);
  const [commissions, setCommissions] = useState<Commission[]>([]);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [dashRes, commRes] = await Promise.all([
        api.get('/affiliate/dashboard'),
        api.get('/affiliate/commissions'),
      ]);
      setDashboard(dashRes.data);
      setCommissions(commRes.data.commissions || []);
    } catch (error) {
      console.error('Error loading affiliate data:', error);
    } finally {
      setLoading(false);
    }
  };

  const requestPayout = async () => {
    try {
      await api.post('/affiliate/payout/request', {
        amount: dashboard?.wallet?.balance || 0,
        payout_method: 'bank_transfer',
        account_details: {},
      });
      loadDashboard();
    } catch (error: any) {
      console.error('Payout error:', error.response?.data?.detail);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#8B5CF6" />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      {/* Stats Cards */}
      <View style={styles.statsRow}>
        <View style={[styles.statCard, { backgroundColor: '#EDE9FE' }]}>
          <Ionicons name="people" size={24} color="#8B5CF6" />
          <Text style={styles.statValue}>{dashboard?.total_referrals || 0}</Text>
          <Text style={styles.statLabel}>Referrals</Text>
        </View>
        <View style={[styles.statCard, { backgroundColor: '#DBEAFE' }]}>
          <Ionicons name="briefcase" size={24} color="#3B82F6" />
          <Text style={styles.statValue}>{dashboard?.total_bookings || 0}</Text>
          <Text style={styles.statLabel}>Bookings</Text>
        </View>
      </View>

      {/* Wallet */}
      <View style={styles.walletCard}>
        <Text style={styles.walletTitle}>Commission Wallet</Text>
        <Text style={styles.walletBalance}>₹{(dashboard?.wallet?.balance || 0).toLocaleString()}</Text>
        <View style={styles.walletRow}>
          <View>
            <Text style={styles.walletLabel}>Pending</Text>
            <Text style={styles.walletSubValue}>₹{(dashboard?.wallet?.pending || 0).toLocaleString()}</Text>
          </View>
          <View>
            <Text style={styles.walletLabel}>Total Earned</Text>
            <Text style={styles.walletSubValue}>₹{(dashboard?.wallet?.total_earned || 0).toLocaleString()}</Text>
          </View>
        </View>
        <TouchableOpacity
          style={styles.payoutButton}
          onPress={requestPayout}
          disabled={(dashboard?.wallet?.balance || 0) < 100}
        >
          <Text style={styles.payoutButtonText}>Request Payout</Text>
        </TouchableOpacity>
      </View>

      {/* Referral Code */}
      <View style={styles.referralCard}>
        <Text style={styles.referralTitle}>Your Referral Code</Text>
        <View style={styles.codeBox}>
          <Text style={styles.codeText}>{dashboard?.referral_code || 'N/A'}</Text>
          <TouchableOpacity>
            <Ionicons name="copy-outline" size={24} color="#8B5CF6" />
          </TouchableOpacity>
        </View>
        <Text style={styles.commissionRate}>
          Earn {dashboard?.commission_rate || 5}% on every booking
        </Text>
      </View>

      {/* Recent Commissions */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Recent Commissions</Text>
        {commissions.length === 0 ? (
          <Text style={styles.emptyText}>No commissions yet</Text>
        ) : (
          commissions.slice(0, 5).map((commission) => (
            <View key={commission.id} style={styles.commissionItem}>
              <View>
                <Text style={styles.commissionBooking}>Booking #{commission.booking_id.slice(0, 8)}</Text>
                <Text style={styles.commissionDate}>
                  {new Date(commission.created_at).toLocaleDateString()}
                </Text>
              </View>
              <View style={styles.commissionRight}>
                <Text style={styles.commissionAmount}>+₹{commission.commission_amount}</Text>
                <Text style={[
                  styles.commissionStatus,
                  { color: commission.status === 'paid' ? '#10B981' : '#F59E0B' }
                ]}>
                  {commission.status}
                </Text>
              </View>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  statsRow: { flexDirection: 'row', padding: 16, gap: 12 },
  statCard: {
    flex: 1,
    padding: 16,
    borderRadius: 16,
    alignItems: 'center',
  },
  statValue: { fontSize: 28, fontWeight: '800', color: '#1F2937', marginTop: 8 },
  statLabel: { fontSize: 14, color: '#6B7280', marginTop: 4 },
  walletCard: {
    backgroundColor: '#8B5CF6',
    marginHorizontal: 16,
    padding: 20,
    borderRadius: 16,
    marginBottom: 16,
  },
  walletTitle: { fontSize: 14, color: '#E9D5FF' },
  walletBalance: { fontSize: 36, fontWeight: '800', color: '#FFFFFF', marginTop: 4 },
  walletRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 16 },
  walletLabel: { fontSize: 12, color: '#E9D5FF' },
  walletSubValue: { fontSize: 18, fontWeight: '700', color: '#FFFFFF', marginTop: 2 },
  payoutButton: {
    backgroundColor: '#FFFFFF',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 16,
  },
  payoutButtonText: { color: '#8B5CF6', fontSize: 16, fontWeight: '700' },
  referralCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    padding: 20,
    borderRadius: 16,
    marginBottom: 16,
  },
  referralTitle: { fontSize: 16, fontWeight: '600', color: '#1F2937' },
  codeBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F3F4F6',
    padding: 16,
    borderRadius: 12,
    marginTop: 12,
  },
  codeText: { fontSize: 24, fontWeight: '800', color: '#8B5CF6', letterSpacing: 2 },
  commissionRate: { fontSize: 14, color: '#6B7280', marginTop: 12, textAlign: 'center' },
  section: { padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: '#1F2937', marginBottom: 12 },
  emptyText: { fontSize: 14, color: '#9CA3AF', textAlign: 'center', paddingVertical: 24 },
  commissionItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    padding: 16,
    borderRadius: 12,
    marginBottom: 8,
  },
  commissionBooking: { fontSize: 14, fontWeight: '600', color: '#1F2937' },
  commissionDate: { fontSize: 12, color: '#6B7280', marginTop: 2 },
  commissionRight: { alignItems: 'flex-end' },
  commissionAmount: { fontSize: 16, fontWeight: '700', color: '#10B981' },
  commissionStatus: { fontSize: 12, marginTop: 2, textTransform: 'capitalize' },
});
