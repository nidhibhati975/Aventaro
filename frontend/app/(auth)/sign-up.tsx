import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../../contexts/AuthContext';

const INTERESTS = [
  'Adventure', 'Beach', 'Culture', 'Food', 'Hiking', 'History',
  'Nightlife', 'Photography', 'Shopping', 'Sports', 'Wildlife'
];

export default function SignUp() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [gender, setGender] = useState('Male');
  const [city, setCity] = useState('');
  const [interests, setInterests] = useState<string[]>([]);
  const [relationshipStatus, setRelationshipStatus] = useState('Single');
  const [loading, setLoading] = useState(false);
  const { signUp } = useAuth();
  const router = useRouter();

  const toggleInterest = (interest: string) => {
    if (interests.includes(interest)) {
      setInterests(interests.filter(i => i !== interest));
    } else {
      setInterests([...interests, interest]);
    }
  };

  const handleSignUp = async () => {
    if (!fullName || !email || !phone || !password || !dateOfBirth || !city || interests.length === 0) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }

    setLoading(true);
    try {
      await signUp({
        full_name: fullName,
        email,
        phone,
        password,
        date_of_birth: dateOfBirth,
        gender,
        city,
        interests,
        relationship_status: relationshipStatus,
      });
      router.replace('/(tabs)/discover');
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <Text style={styles.title}>Welcome to Aventaro</Text>
          <Text style={styles.subtitle}>Create your account</Text>

          <View style={styles.form}>
            <View style={styles.inputContainer}>
              <Text style={styles.label}>Full Name *</Text>
              <TextInput
                style={styles.input}
                placeholder="Enter your full name"
                value={fullName}
                onChangeText={setFullName}
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.label}>Email *</Text>
              <TextInput
                style={styles.input}
                placeholder="Enter your email"
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.label}>Phone *</Text>
              <TextInput
                style={styles.input}
                placeholder="Enter your phone number"
                value={phone}
                onChangeText={setPhone}
                keyboardType="phone-pad"
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.label}>Password *</Text>
              <TextInput
                style={styles.input}
                placeholder="Create a password"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.label}>Date of Birth *</Text>
              <TextInput
                style={styles.input}
                placeholder="YYYY-MM-DD"
                value={dateOfBirth}
                onChangeText={setDateOfBirth}
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.label}>Gender *</Text>
              <View style={styles.pickerContainer}>
                <Picker
                  selectedValue={gender}
                  onValueChange={(value) => setGender(value)}
                  style={styles.picker}
                >
                  <Picker.Item label="Male" value="Male" />
                  <Picker.Item label="Female" value="Female" />
                  <Picker.Item label="Other" value="Other" />
                </Picker>
              </View>
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.label}>City *</Text>
              <TextInput
                style={styles.input}
                placeholder="Enter your city"
                value={city}
                onChangeText={setCity}
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.label}>Relationship Status *</Text>
              <View style={styles.pickerContainer}>
                <Picker
                  selectedValue={relationshipStatus}
                  onValueChange={(value) => setRelationshipStatus(value)}
                  style={styles.picker}
                >
                  <Picker.Item label="Single" value="Single" />
                  <Picker.Item label="Married" value="Married" />
                  <Picker.Item label="Widowed" value="Widowed" />
                  <Picker.Item label="Divorced" value="Divorced" />
                </Picker>
              </View>
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.label}>Interests * (Select at least one)</Text>
              <View style={styles.interestsContainer}>
                {INTERESTS.map((interest) => (
                  <TouchableOpacity
                    key={interest}
                    style={[
                      styles.interestChip,
                      interests.includes(interest) && styles.interestChipSelected,
                    ]}
                    onPress={() => toggleInterest(interest)}
                  >
                    <Text
                      style={[
                        styles.interestText,
                        interests.includes(interest) && styles.interestTextSelected,
                      ]}
                    >
                      {interest}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleSignUp}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.buttonText}>Sign Up</Text>
              )}
            </TouchableOpacity>

            <View style={styles.footer}>
              <Text style={styles.footerText}>Already have an account? </Text>
              <TouchableOpacity onPress={() => router.back()}>
                <Text style={styles.footerLink}>Sign In</Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    padding: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 16,
    color: '#6B7280',
    marginBottom: 24,
    textAlign: 'center',
  },
  form: {
    gap: 16,
  },
  inputContainer: {
    gap: 8,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
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
  pickerContainer: {
    backgroundColor: '#F9FAFB',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    borderRadius: 12,
    overflow: 'hidden',
  },
  picker: {
    height: 50,
  },
  interestsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  interestChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#F3F4F6',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  interestChipSelected: {
    backgroundColor: '#8B5CF6',
    borderColor: '#8B5CF6',
  },
  interestText: {
    fontSize: 14,
    color: '#6B7280',
  },
  interestTextSelected: {
    color: '#FFFFFF',
  },
  button: {
    backgroundColor: '#8B5CF6',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 16,
    marginBottom: 32,
  },
  footerText: {
    color: '#6B7280',
    fontSize: 14,
  },
  footerLink: {
    color: '#8B5CF6',
    fontSize: 14,
    fontWeight: '600',
  },
});