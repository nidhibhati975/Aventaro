import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Dimensions,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';

const { width } = Dimensions.get('window');
const CARD_WIDTH = width - 48;

export default function Discover() {
  const [activeTab, setActiveTab] = useState<'people' | 'trips'>('people');
  const [people, setPeople] = useState<any[]>([]);
  const [trips, setTrips] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const { user } = useAuth();

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'people') {
        const response = await api.get('/users/discover');
        setPeople(response.data);
        setCurrentIndex(0);
      } else {
        const response = await api.get('/trips/discover');
        setTrips(response.data);
        setCurrentIndex(0);
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSwipeLeft = () => {
    // Skip
    if (activeTab === 'people') {
      if (currentIndex < people.length - 1) {
        setCurrentIndex(currentIndex + 1);
      } else {
        Alert.alert('No More', 'No more people to discover');
      }
    } else {
      if (currentIndex < trips.length - 1) {
        setCurrentIndex(currentIndex + 1);
      } else {
        Alert.alert('No More', 'No more trips to discover');
      }
    }
  };

  const handleSwipeRight = async () => {
    try {
      if (activeTab === 'people') {
        const person = people[currentIndex];
        await api.post(`/api/users/friend-request?to_user_id=${person.id}`);
        Alert.alert('Success', 'Friend request sent!');
        if (currentIndex < people.length - 1) {
          setCurrentIndex(currentIndex + 1);
        }
      } else {
        const trip = trips[currentIndex];
        await api.post(`/api/trips/${trip.id}/join-request`);
        Alert.alert('Success', 'Trip join request sent!');
        if (currentIndex < trips.length - 1) {
          setCurrentIndex(currentIndex + 1);
        }
      }
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Action failed');
    }
  };

  const renderPeopleCard = (person: any) => {
    if (!person) return null;

    return (
      <View style={styles.card}>
        <View style={styles.cardImageContainer}>
          {person.profile_image ? (
            <Image source={{ uri: person.profile_image }} style={styles.cardImage} />
          ) : (
            <View style={[styles.cardImage, styles.placeholderImage]}>
              <Ionicons name="person" size={80} color="#D1D5DB" />
            </View>
          )}
        </View>

        <View style={styles.cardContent}>
          <Text style={styles.cardName}>
            {person.full_name}, {person.date_of_birth ? new Date().getFullYear() - new Date(person.date_of_birth).getFullYear() : '?'}
          </Text>
          <Text style={styles.cardDetail}>
            <Ionicons name="location" size={14} color="#6B7280" /> {person.city}
          </Text>
          <Text style={styles.cardDetail}>
            <Ionicons name="heart" size={14} color="#6B7280" /> {person.relationship_status}
          </Text>
          
          {person.bio && <Text style={styles.cardBio}>{person.bio}</Text>}
          
          <View style={styles.interestsContainer}>
            {person.interests?.map((interest: string, index: number) => (
              <View key={index} style={styles.interestTag}>
                <Text style={styles.interestText}>{interest}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>
    );
  };

  const renderTripsCard = (trip: any) => {
    if (!trip) return null;

    return (
      <View style={styles.card}>
        <View style={styles.cardImageContainer}>
          {trip.trip_image ? (
            <Image source={{ uri: trip.trip_image }} style={styles.cardImage} />
          ) : (
            <View style={[styles.cardImage, styles.placeholderImage]}>
              <Ionicons name="airplane" size={80} color="#D1D5DB" />
            </View>
          )}
          {trip.is_boosted && (
            <View style={styles.boostedBadge}>
              <Ionicons name="flash" size={16} color="#F59E0B" />
              <Text style={styles.boostedText}>Boosted</Text>
            </View>
          )}
        </View>

        <View style={styles.cardContent}>
          <Text style={styles.cardName}>{trip.destination}</Text>
          <Text style={styles.cardDetail}>
            <Ionicons name="calendar" size={14} color="#6B7280" /> {trip.start_date} - {trip.end_date}
          </Text>
          <Text style={styles.cardDetail}>
            <Ionicons name="cash" size={14} color="#6B7280" /> Budget: {trip.budget_range}
          </Text>
          <Text style={styles.cardDetail}>
            <Ionicons name="people" size={14} color="#6B7280" /> Max {trip.max_members} members
          </Text>
          <Text style={styles.cardDetail}>
            <Ionicons name="location" size={14} color="#6B7280" /> {trip.trip_type}
          </Text>
          
          {trip.creator && (
            <View style={styles.creatorContainer}>
              <Text style={styles.creatorLabel}>Created by:</Text>
              <Text style={styles.creatorName}>{trip.creator.full_name}</Text>
            </View>
          )}

          {trip.itinerary && (
            <View style={styles.itineraryContainer}>
              <Text style={styles.itineraryTitle}>Itinerary:</Text>
              <Text style={styles.itineraryText} numberOfLines={3}>{trip.itinerary}</Text>
            </View>
          )}
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Image
          source={require('../../assets/images/aventaro-logo.png')}
          style={styles.logo}
          resizeMode="contain"
        />
        <View style={styles.headerIcons}>
          <TouchableOpacity style={styles.headerIcon}>
            <Ionicons name="notifications-outline" size={24} color="#1F2937" />
          </TouchableOpacity>
          <TouchableOpacity style={styles.headerIcon}>
            <Ionicons name="shield-checkmark-outline" size={24} color="#1F2937" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabsContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'people' && styles.tabActive]}
          onPress={() => setActiveTab('people')}
        >
          <Text style={[styles.tabText, activeTab === 'people' && styles.tabTextActive]}>
            Discover People
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'trips' && styles.tabActive]}
          onPress={() => setActiveTab('trips')}
        >
          <Text style={[styles.tabText, activeTab === 'trips' && styles.tabTextActive]}>
            Discover Trips
          </Text>
        </TouchableOpacity>
      </View>

      {/* Content */}
      <ScrollView style={styles.content}>
        {loading ? (
          <ActivityIndicator size="large" color="#8B5CF6" style={{ marginTop: 100 }} />
        ) : (
          <View style={styles.cardContainer}>
            {activeTab === 'people'
              ? renderPeopleCard(people[currentIndex])
              : renderTripsCard(trips[currentIndex])}

            {/* Action Buttons */}
            {((activeTab === 'people' && people.length > 0) || (activeTab === 'trips' && trips.length > 0)) && (
              <View style={styles.actionsContainer}>
                <TouchableOpacity style={styles.skipButton} onPress={handleSwipeLeft}>
                  <Ionicons name="close" size={32} color="#EF4444" />
                </TouchableOpacity>
                <TouchableOpacity style={styles.likeButton} onPress={handleSwipeRight}>
                  <Ionicons
                    name={activeTab === 'people' ? 'heart' : 'add-circle'}
                    size={32}
                    color="#10B981"
                  />
                </TouchableOpacity>
              </View>
            )}

            {((activeTab === 'people' && people.length === 0) || (activeTab === 'trips' && trips.length === 0)) && (
              <View style={styles.emptyState}>
                <Ionicons name="search" size={64} color="#D1D5DB" />
                <Text style={styles.emptyText}>
                  No {activeTab === 'people' ? 'people' : 'trips'} to discover right now
                </Text>
              </View>
            )}
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
  logo: {
    width: 40,
    height: 40,
  },
  headerIcons: {
    flexDirection: 'row',
    gap: 16,
  },
  headerIcon: {
    padding: 4,
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
  },
  cardContainer: {
    paddingHorizontal: 24,
    paddingTop: 24,
    alignItems: 'center',
  },
  card: {
    width: CARD_WIDTH,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 5,
    overflow: 'hidden',
  },
  cardImageContainer: {
    position: 'relative',
  },
  cardImage: {
    width: '100%',
    height: 300,
    backgroundColor: '#F3F4F6',
  },
  placeholderImage: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  boostedBadge: {
    position: 'absolute',
    top: 16,
    right: 16,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFBEB',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    gap: 4,
  },
  boostedText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#F59E0B',
  },
  cardContent: {
    padding: 20,
  },
  cardName: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: 12,
  },
  cardDetail: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 8,
  },
  cardBio: {
    fontSize: 14,
    color: '#374151',
    marginTop: 12,
    lineHeight: 20,
  },
  interestsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
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
  creatorContainer: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  creatorLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 4,
  },
  creatorName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1F2937',
  },
  itineraryContainer: {
    marginTop: 12,
    padding: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
  },
  itineraryTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 4,
  },
  itineraryText: {
    fontSize: 13,
    color: '#374151',
    lineHeight: 18,
  },
  actionsContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 32,
    marginTop: 32,
    marginBottom: 32,
  },
  skipButton: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#FEE2E2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  likeButton: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#D1FAE5',
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