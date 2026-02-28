import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
  Dimensions,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import {
  BookingCategoryCard,
  BookingItemCard,
  SearchBar,
  BookingListHeader,
  EmptyState,
  BookingCategory,
  BookingItemData,
} from '../../components/booking';

const { width } = Dimensions.get('window');

// =====================
// BOOKING CATEGORIES
// =====================
const BOOKING_CATEGORIES: BookingCategory[] = [
  {
    id: 'hotels',
    name: 'Hotels',
    icon: 'bed',
    color: '#8B5CF6',
    bgColor: '#EDE9FE',
    serviceType: 'hotel',
  },
  {
    id: 'flights',
    name: 'Flights',
    icon: 'airplane',
    color: '#3B82F6',
    bgColor: '#DBEAFE',
    serviceType: 'flight',
  },
  {
    id: 'villas',
    name: 'Villas',
    icon: 'home',
    color: '#10B981',
    bgColor: '#D1FAE5',
    serviceType: 'villa',
  },
  {
    id: 'cabs',
    name: 'Cabs',
    icon: 'car',
    color: '#F59E0B',
    bgColor: '#FEF3C7',
    serviceType: 'cab',
  },
  {
    id: 'trains',
    name: 'Trains',
    icon: 'train',
    color: '#EF4444',
    bgColor: '#FEE2E2',
    serviceType: 'train',
  },
  {
    id: 'buses',
    name: 'Buses',
    icon: 'bus',
    color: '#6366F1',
    bgColor: '#E0E7FF',
    serviceType: 'bus',
  },
  {
    id: 'activities',
    name: 'Activities',
    icon: 'compass',
    color: '#EC4899',
    bgColor: '#FCE7F3',
    serviceType: 'activity',
  },
  {
    id: 'apartments',
    name: 'Apartments',
    icon: 'business',
    color: '#14B8A6',
    bgColor: '#CCFBF1',
    serviceType: 'apartment',
  },
  {
    id: 'packages',
    name: 'Packages',
    icon: 'gift',
    color: '#A855F7',
    bgColor: '#F3E8FF',
    serviceType: 'package',
  },
];

// =====================
// VIEW STATES
// =====================
type ViewState = 'categories' | 'search' | 'list';

export default function Booking() {
  const { user } = useAuth();
  
  // State
  const [viewState, setViewState] = useState<ViewState>('categories');
  const [selectedCategory, setSelectedCategory] = useState<BookingCategory | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<BookingItemData[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [totalResults, setTotalResults] = useState(0);

  // =====================
  // API CALLS
  // =====================
  const fetchListings = useCallback(async (
    serviceType: string,
    destination?: string,
    pageNum: number = 1,
    append: boolean = false
  ) => {
    try {
      setLoading(true);
      
      const params = new URLSearchParams({
        page: pageNum.toString(),
        limit: '20',
      });
      
      if (destination) {
        params.append('destination', destination);
      }
      
      const response = await api.get(
        `/booking/search/${serviceType}?${params.toString()}`
      );
      
      const { results, total, has_more } = response.data;
      
      if (append) {
        setSearchResults(prev => [...prev, ...results]);
      } else {
        setSearchResults(results);
      }
      
      setTotalResults(total);
      setHasMore(has_more);
      setPage(pageNum);
    } catch (error: any) {
      console.error('Error fetching listings:', error);
      // Show empty state if API fails
      if (!append) {
        setSearchResults([]);
        setTotalResults(0);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // =====================
  // HANDLERS
  // =====================
  const handleCategoryPress = (category: BookingCategory) => {
    setSelectedCategory(category);
    setViewState('list');
    setSearchQuery('');
    setPage(1);
    fetchListings(category.serviceType);
  };

  const handleSearch = () => {
    if (selectedCategory && searchQuery.trim()) {
      setPage(1);
      fetchListings(selectedCategory.serviceType, searchQuery.trim());
    }
  };

  const handleBack = () => {
    setViewState('categories');
    setSelectedCategory(null);
    setSearchResults([]);
    setSearchQuery('');
    setPage(1);
    setTotalResults(0);
  };

  const handleRefresh = () => {
    setRefreshing(true);
    if (selectedCategory) {
      setPage(1);
      fetchListings(selectedCategory.serviceType, searchQuery || undefined, 1, false);
    }
  };

  const handleLoadMore = () => {
    if (!loading && hasMore && selectedCategory) {
      const nextPage = page + 1;
      fetchListings(
        selectedCategory.serviceType,
        searchQuery || undefined,
        nextPage,
        true
      );
    }
  };

  const handleItemPress = (item: BookingItemData) => {
    // Navigate to booking detail (to be implemented)
    Alert.alert(
      item.name,
      `Price: ${item.currency} ${item.price.toLocaleString()}\n\nBooking details & payment flow coming soon!`,
      [{ text: 'OK' }]
    );
  };

  // =====================
  // RENDER SECTIONS
  // =====================
  const renderCategoriesView = () => (
    <ScrollView
      style={styles.scrollView}
      contentContainerStyle={styles.scrollContent}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => {}} />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Book Your Journey</Text>
        <Text style={styles.headerSubtitle}>
          Hotels, flights, cabs & more at the best prices
        </Text>
      </View>

      {/* Quick Search */}
      <View style={styles.searchContainer}>
        <SearchBar
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholder="Where do you want to go?"
          onSearch={() => {
            if (searchQuery.trim()) {
              // Default to hotels for general search
              setSelectedCategory(BOOKING_CATEGORIES[0]);
              setViewState('list');
              fetchListings('hotel', searchQuery.trim());
            }
          }}
        />
      </View>

      {/* Categories Grid */}
      <View style={styles.sectionContainer}>
        <Text style={styles.sectionTitle}>Browse Categories</Text>
        <View style={styles.categoriesGrid}>
          {BOOKING_CATEGORIES.map((category) => (
            <BookingCategoryCard
              key={category.id}
              category={category}
              onPress={handleCategoryPress}
            />
          ))}
        </View>
      </View>

      {/* Quick Stats */}
      <View style={styles.statsContainer}>
        <View style={styles.statItem}>
          <Ionicons name="shield-checkmark" size={24} color="#10B981" />
          <Text style={styles.statLabel}>Secure Payments</Text>
        </View>
        <View style={styles.statItem}>
          <Ionicons name="time" size={24} color="#8B5CF6" />
          <Text style={styles.statLabel}>24/7 Support</Text>
        </View>
        <View style={styles.statItem}>
          <Ionicons name="pricetag" size={24} color="#F59E0B" />
          <Text style={styles.statLabel}>Best Prices</Text>
        </View>
      </View>

      {/* My Bookings Quick Access */}
      <TouchableOpacity
        style={styles.myBookingsButton}
        onPress={() => {
          Alert.alert('My Bookings', 'Booking history coming soon!');
        }}
      >
        <View style={styles.myBookingsContent}>
          <Ionicons name="document-text" size={24} color="#8B5CF6" />
          <View style={styles.myBookingsText}>
            <Text style={styles.myBookingsTitle}>My Bookings</Text>
            <Text style={styles.myBookingsSubtitle}>View your travel history</Text>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={24} color="#9CA3AF" />
      </TouchableOpacity>
    </ScrollView>
  );

  const renderListView = () => (
    <View style={styles.listContainer}>
      {/* Header */}
      <BookingListHeader
        title={selectedCategory?.name || 'Results'}
        onBack={handleBack}
        resultCount={totalResults}
      />

      {/* Search within category */}
      <View style={styles.listSearchContainer}>
        <SearchBar
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholder={`Search ${selectedCategory?.name.toLowerCase() || ''}...`}
          onSearch={handleSearch}
        />
      </View>

      {/* Results List */}
      <ScrollView
        style={styles.resultsScrollView}
        contentContainerStyle={styles.resultsContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
        onMomentumScrollEnd={({ nativeEvent }) => {
          const { layoutMeasurement, contentOffset, contentSize } = nativeEvent;
          const isEndReached =
            layoutMeasurement.height + contentOffset.y >= contentSize.height - 50;
          if (isEndReached) {
            handleLoadMore();
          }
        }}
      >
        {loading && searchResults.length === 0 ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#8B5CF6" />
            <Text style={styles.loadingText}>Finding the best deals...</Text>
          </View>
        ) : searchResults.length === 0 ? (
          <EmptyState
            icon="search-outline"
            title="No Results Found"
            message={`We couldn't find any ${selectedCategory?.name.toLowerCase() || 'items'}. Try adjusting your search or check back later.`}
          />
        ) : (
          <>
            {searchResults.map((item) => (
              <BookingItemCard
                key={item.id}
                item={item}
                onPress={handleItemPress}
              />
            ))}
            
            {loading && searchResults.length > 0 && (
              <View style={styles.loadMoreContainer}>
                <ActivityIndicator size="small" color="#8B5CF6" />
              </View>
            )}
            
            {!hasMore && searchResults.length > 0 && (
              <Text style={styles.endOfList}>No more results</Text>
            )}
          </>
        )}
      </ScrollView>
    </View>
  );

  // =====================
  // MAIN RENDER
  // =====================
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {viewState === 'categories' && renderCategoriesView()}
      {viewState === 'list' && renderListView()}
    </SafeAreaView>
  );
}

// =====================
// STYLES
// =====================
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 32,
  },
  header: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 24,
    backgroundColor: '#8B5CF6',
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#E9D5FF',
  },
  searchContainer: {
    paddingHorizontal: 24,
    marginTop: -24,
    marginBottom: 24,
  },
  sectionContainer: {
    paddingHorizontal: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1F2937',
    marginBottom: 16,
  },
  categoriesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  statsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingHorizontal: 24,
    paddingVertical: 24,
    marginTop: 16,
    backgroundColor: '#FFFFFF',
    marginHorizontal: 24,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  statItem: {
    alignItems: 'center',
  },
  statLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 8,
    textAlign: 'center',
  },
  myBookingsButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    marginHorizontal: 24,
    marginTop: 24,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  myBookingsContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  myBookingsText: {
    marginLeft: 16,
  },
  myBookingsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
  },
  myBookingsSubtitle: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  listContainer: {
    flex: 1,
  },
  listSearchContainer: {
    padding: 16,
    backgroundColor: '#FFFFFF',
  },
  resultsScrollView: {
    flex: 1,
  },
  resultsContent: {
    padding: 16,
    paddingBottom: 32,
  },
  loadingContainer: {
    alignItems: 'center',
    paddingVertical: 64,
  },
  loadingText: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 16,
  },
  loadMoreContainer: {
    paddingVertical: 16,
    alignItems: 'center',
  },
  endOfList: {
    textAlign: 'center',
    fontSize: 13,
    color: '#9CA3AF',
    paddingVertical: 16,
  },
});
