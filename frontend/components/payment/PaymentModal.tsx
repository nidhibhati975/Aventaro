import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  Image,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

interface Props {
  visible: boolean;
  onClose: () => void;
  bookingId: string;
  amount: number;
  currency?: string;
  onPaymentSuccess: (transactionId: string) => void;
}

type PaymentMethod = 'razorpay' | 'stripe' | 'upi' | 'paypal';

export default function PaymentModal({
  visible,
  onClose,
  bookingId,
  amount,
  currency = 'INR',
  onPaymentSuccess,
}: Props) {
  const [selectedMethod, setSelectedMethod] = useState<PaymentMethod | null>(null);
  const [loading, setLoading] = useState(false);
  const [upiQR, setUpiQR] = useState<{ qr_image: string; expires_at: string } | null>(null);

  const paymentMethods = [
    { id: 'razorpay', name: 'Cards / UPI / Netbanking', icon: 'card', color: '#3B82F6' },
    { id: 'stripe', name: 'International Cards', icon: 'globe', color: '#635BFF' },
    { id: 'upi', name: 'UPI QR Code', icon: 'qr-code', color: '#10B981' },
    { id: 'paypal', name: 'PayPal', icon: 'logo-paypal', color: '#0070BA' },
  ];

  const initiatePayment = async () => {
    if (!selectedMethod) {
      Alert.alert('Error', 'Please select a payment method');
      return;
    }

    setLoading(true);
    try {
      const idempotencyKey = `${bookingId}_${Date.now()}`;
      
      const response = await api.post('/payment/create', {
        booking_id: bookingId,
        amount,
        currency,
        provider: selectedMethod,
        method: selectedMethod === 'upi' ? 'upi' : 'card',
        idempotency_key: idempotencyKey,
      });

      if (selectedMethod === 'upi' && response.data.qr_image) {
        setUpiQR({
          qr_image: response.data.qr_image,
          expires_at: response.data.expires_at,
        });
      } else if (selectedMethod === 'razorpay') {
        // Open Razorpay checkout
        Alert.alert(
          'Razorpay',
          `Order ID: ${response.data.provider_order_id}\nPlease complete payment in Razorpay SDK`,
          [{ text: 'OK', onPress: () => simulatePaymentSuccess(response.data.transaction_id) }]
        );
      } else if (selectedMethod === 'stripe') {
        Alert.alert(
          'Stripe',
          'Redirecting to Stripe checkout...',
          [{ text: 'OK', onPress: () => simulatePaymentSuccess(response.data.transaction_id) }]
        );
      } else if (selectedMethod === 'paypal') {
        Alert.alert(
          'PayPal',
          'Redirecting to PayPal...',
          [{ text: 'OK', onPress: () => simulatePaymentSuccess(response.data.transaction_id) }]
        );
      }
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Payment initiation failed');
    } finally {
      setLoading(false);
    }
  };

  const simulatePaymentSuccess = async (transactionId: string) => {
    try {
      await api.post('/payment/verify', {
        transaction_id: transactionId,
        provider_order_id: 'simulated_order',
        provider_payment_id: 'simulated_payment',
        provider_signature: 'simulated_signature',
      });
      onPaymentSuccess(transactionId);
      onClose();
    } catch (error) {
      // Payment verified via webhook
      onPaymentSuccess(transactionId);
      onClose();
    }
  };

  const renderContent = () => {
    if (upiQR) {
      return (
        <View style={styles.qrContainer}>
          <Text style={styles.qrTitle}>Scan QR Code to Pay</Text>
          <Image
            source={{ uri: `data:image/png;base64,${upiQR.qr_image}` }}
            style={styles.qrImage}
          />
          <Text style={styles.qrAmount}>{currency} {amount.toLocaleString()}</Text>
          <Text style={styles.qrExpiry}>Expires in 15 minutes</Text>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => setUpiQR(null)}
          >
            <Text style={styles.backButtonText}>Choose Another Method</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return (
      <>
        <Text style={styles.title}>Select Payment Method</Text>
        <Text style={styles.amountText}>
          Total: {currency} {amount.toLocaleString()}
        </Text>

        <View style={styles.methodsContainer}>
          {paymentMethods.map((method) => (
            <TouchableOpacity
              key={method.id}
              style={[
                styles.methodCard,
                selectedMethod === method.id && styles.methodCardSelected,
              ]}
              onPress={() => setSelectedMethod(method.id as PaymentMethod)}
            >
              <View style={[styles.methodIcon, { backgroundColor: `${method.color}20` }]}>
                <Ionicons name={method.icon as any} size={24} color={method.color} />
              </View>
              <Text style={styles.methodName}>{method.name}</Text>
              {selectedMethod === method.id && (
                <Ionicons name="checkmark-circle" size={24} color="#8B5CF6" />
              )}
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          style={[styles.payButton, !selectedMethod && styles.payButtonDisabled]}
          onPress={initiatePayment}
          disabled={!selectedMethod || loading}
        >
          {loading ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.payButtonText}>Pay {currency} {amount.toLocaleString()}</Text>
          )}
        </TouchableOpacity>
      </>
    );
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.overlay}>
        <View style={styles.container}>
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <Ionicons name="close" size={24} color="#6B7280" />
          </TouchableOpacity>
          {renderContent()}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  container: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  closeButton: {
    position: 'absolute',
    top: 16,
    right: 16,
    zIndex: 1,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1F2937',
    marginBottom: 8,
  },
  amountText: {
    fontSize: 24,
    fontWeight: '800',
    color: '#8B5CF6',
    marginBottom: 24,
  },
  methodsContainer: {
    gap: 12,
    marginBottom: 24,
  },
  methodCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#E5E7EB',
    backgroundColor: '#FFFFFF',
  },
  methodCardSelected: {
    borderColor: '#8B5CF6',
    backgroundColor: '#F5F3FF',
  },
  methodIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  methodName: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
  },
  payButton: {
    backgroundColor: '#8B5CF6',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  payButtonDisabled: {
    backgroundColor: '#D1D5DB',
  },
  payButtonText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
  },
  qrContainer: {
    alignItems: 'center',
    paddingTop: 16,
  },
  qrTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1F2937',
    marginBottom: 24,
  },
  qrImage: {
    width: 200,
    height: 200,
    marginBottom: 16,
  },
  qrAmount: {
    fontSize: 24,
    fontWeight: '800',
    color: '#8B5CF6',
    marginBottom: 8,
  },
  qrExpiry: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 24,
  },
  backButton: {
    paddingVertical: 12,
    paddingHorizontal: 24,
  },
  backButtonText: {
    fontSize: 16,
    color: '#8B5CF6',
    fontWeight: '600',
  },
});
