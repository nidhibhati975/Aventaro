import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';

export default function Trips() {
  const [activeTab, setActiveTab] = useState<'created' | 'joined'>('created');
  const [createdTrips, setCreatedTrips] = useState<any[]>([]);
  const [joinedTrips, setJoinedTrips] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const router = useRouter();

  // Form states
  const [destination, setDestination] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [budgetRange, setBudgetRange] = useState('');
  const [tripType, setTripType] = useState('');
  const [maxMembers, setMaxMembers] = useState('10');
  const [itinerary, setItinerary] = useState('');

  useEffect(() => {
    loadTrips();
  }, []);

  const loadTrips = async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/trips/my-trips');
      setCreatedTrips(response.data.created || []);
      setJoinedTrips(response.data.joined || []);
    } catch (error) {
      console.error('Error loading trips:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTrip = async () => {
    if (!destination || !startDate || !endDate || !budgetRange || !tripType || !itinerary) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    try {
      await api.post('/api/trips', {
        destination,
        start_date: startDate,
        end_date: endDate,
        budget_range: budgetRange,
        trip_type: tripType,
        max_members: parseInt(maxMembers),
        itinerary,
      });

      Alert.alert('Success', 'Trip created successfully!');
      setShowCreateForm(false);
      // Reset form
      setDestination('');
      setStartDate('');
      setEndDate('');
      setBudgetRange('');
      setTripType('');
      setMaxMembers('10');
      setItinerary('');
      loadTrips();
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to create trip');
    }
  };

  const renderTripCard = (trip: any) => (
    <View key={trip.id} style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>{trip.destination}</Text>
        {trip.is_boosted && (
          <View style={styles.boostedBadge}>
            <Ionicons name="flash" size={12} color="#F59E0B" />
            <Text style={styles.boostedText}>Boosted</Text>
          </View>
        )}
      </View>
      
      <View style={styles.cardDetails}>
        <View style={styles.cardDetailRow}>
          <Ionicons name="calendar" size={14} color="#6B7280" />
          <Text style={styles.cardDetailText}>
            {trip.start_date} - {trip.end_date}
          </Text>
        </View>
        <View style={styles.cardDetailRow}>
          <Ionicons name="cash" size={14} color="#6B7280" />
          <Text style={styles.cardDetailText}>Budget: {trip.budget_range}</Text>
        </View>
        <View style={styles.cardDetailRow}>
          <Ionicons name="people" size={14} color="#6B7280" />
          <Text style={styles.cardDetailText}>
            {trip.members?.length || 1}/{trip.max_members} members
          </Text>
        </View>
      </View>

      {trip.itinerary && (
        <Text style={styles.cardItinerary} numberOfLines={2}>
          {trip.itinerary}
        </Text>
      )}
    </View>
  );

  if (showCreateForm) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => setShowCreateForm(false)}>
            <Ionicons name="arrow-back" size={24} color="#1F2937" />
          </TouchableOpacity>
          <Text style={styles.title}>Create Trip</Text>
          <View style={{ width: 24 }} />
        </View>

        <ScrollView style={styles.formContainer}>
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Destination *</Text>
            <TextInput
              style={styles.input}
              placeholder="Enter destination"
              value={destination}
              onChangeText={setDestination}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Start Date * (YYYY-MM-DD)</Text>
            <TextInput
              style={styles.input}
              placeholder="2024-01-01"
              value={startDate}
              onChangeText={setStartDate}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>End Date * (YYYY-MM-DD)</Text>
            <TextInput
              style={styles.input}
              placeholder="2024-01-07"
              value={endDate}
              onChangeText={setEndDate}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Budget Range *</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g., ₹50,000 - ₹100,000"
              value={budgetRange}
              onChangeText={setBudgetRange}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Trip Type *</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g., Adventure, Beach, Cultural"
              value={tripType}
              onChangeText={setTripType}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Max Members *</Text>
            <TextInput
              style={styles.input}
              placeholder="10"
              value={maxMembers}
              onChangeText={setMaxMembers}
              keyboardType="number-pad"
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Itinerary * (Describe your trip plan)</Text>
            <TextInput
              style={[styles.input, styles.textArea]}
              placeholder="Describe your trip itinerary..."
              value={itinerary}
              onChangeText={setItinerary}
              multiline
              numberOfLines={6}
              textAlignVertical="top"
            />
          </View>

          <TouchableOpacity style={styles.createButton} onPress={handleCreateTrip}>
            <Text style={styles.createButtonText}>Create Trip</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>My Trips</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => setShowCreateForm(true)}
        >
          <Ionicons name="add" size={24} color="#FFFFFF" />
        </TouchableOpacity>
      </View>

      <View style={styles.tabsContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'created' && styles.tabActive]}
          onPress={() => setActiveTab('created')}
        >
          <Text style={[styles.tabText, activeTab === 'created' && styles.tabTextActive]}>
            Created
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'joined' && styles.tabActive]}
          onPress={() => setActiveTab('joined')}
        >
          <Text style={[styles.tabText, activeTab === 'joined' && styles.tabTextActive]}>
            Joined
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content}>
        {loading ? (
          <ActivityIndicator size="large" color="#8B5CF6" style={{ marginTop: 32 }} />
        ) : activeTab === 'created' ? (
          createdTrips.length > 0 ? (
            createdTrips.map(renderTripCard)
          ) : (
            <View style={styles.emptyState}>
              <Ionicons name="airplane-outline" size={64} color="#D1D5DB" />
              <Text style={styles.emptyText}>No trips created yet</Text>
              <TouchableOpacity
                style={styles.emptyButton}
                onPress={() => setShowCreateForm(true)}
              >
                <Text style={styles.emptyButtonText}>Create Your First Trip</Text>
              </TouchableOpacity>
            </View>
          )
        ) : joinedTrips.length > 0 ? (
          joinedTrips.map(renderTripCard)
        ) : (
          <View style={styles.emptyState}>
            <Ionicons name="people-outline" size={64} color="#D1D5DB" />
            <Text style={styles.emptyText}>No trips joined yet</Text>
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
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
  addButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#8B5CF6',
    justifyContent: 'center',
    alignItems: 'center',
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
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1F2937',
    flex: 1,
  },
  boostedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFBEB',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    gap: 4,
  },
  boostedText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#F59E0B',
  },
  cardDetails: {
    gap: 8,
  },
  cardDetailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  cardDetailText: {
    fontSize: 14,
    color: '#6B7280',
  },
  cardItinerary: {
    fontSize: 13,
    color: '#374151',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 16,
    color: '#9CA3AF',
    marginTop: 16,
    marginBottom: 24,
  },
  emptyButton: {
    backgroundColor: '#8B5CF6',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  emptyButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  formContainer: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 16,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#F9FAFB',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#1F2937',
  },
  textArea: {
    height: 120,
  },
  createButton: {
    backgroundColor: '#8B5CF6',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginVertical: 24,
  },
  createButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
});