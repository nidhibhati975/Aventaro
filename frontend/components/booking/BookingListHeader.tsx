import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface Props {
  title: string;
  onBack: () => void;
  resultCount?: number;
}

export default function BookingListHeader({ title, onBack, resultCount }: Props) {
  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.backButton} onPress={onBack}>
        <Ionicons name="arrow-back" size={24} color="#1F2937" />
      </TouchableOpacity>
      <View style={styles.titleContainer}>
        <Text style={styles.title}>{title}</Text>
        {resultCount !== undefined && (
          <Text style={styles.resultCount}>{resultCount} results found</Text>
        )}
      </View>
      <TouchableOpacity style={styles.filterButton}>
        <Ionicons name="options-outline" size={22} color="#1F2937" />
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backButton: {
    padding: 8,
    marginRight: 8,
  },
  titleContainer: {
    flex: 1,
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1F2937',
  },
  resultCount: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  filterButton: {
    padding: 8,
  },
});
