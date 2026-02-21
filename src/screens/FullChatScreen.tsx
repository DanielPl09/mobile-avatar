import React, { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Easing,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import ChatBubble, { TypingIndicator } from '../components/ChatBubble';
import ChatInput from '../components/ChatInput';
import { FullChatNavProp, FullChatRouteProp, Message } from '../types';
import { getAIResponse } from '../data/mockResponses';

export default function FullChatScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<FullChatNavProp>();
  const { params } = useRoute<FullChatRouteProp>();
  const { avatar, initialMessages } = params;

  const [messages, setMessages] = useState<Message[]>(initialMessages ?? []);
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  // Avatar badge animations
  const badgePulse = useRef(new Animated.Value(1)).current;
  const badgeGlow = useRef(new Animated.Value(0.4)).current;
  // Header entrance
  const headerFade = useRef(new Animated.Value(0)).current;
  const headerSlide = useRef(new Animated.Value(-12)).current;

  useEffect(() => {
    // Header slides in
    Animated.parallel([
      Animated.timing(headerFade, { toValue: 1, duration: 380, useNativeDriver: true }),
      Animated.timing(headerSlide, { toValue: 0, duration: 340, useNativeDriver: true }),
    ]).start();

    // Badge breathe loop
    Animated.loop(
      Animated.sequence([
        Animated.timing(badgePulse, { toValue: 1.08, duration: 1800, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(badgePulse, { toValue: 1, duration: 1800, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ])
    ).start();

    Animated.loop(
      Animated.sequence([
        Animated.timing(badgeGlow, { toValue: 0.9, duration: 2000, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(badgeGlow, { toValue: 0.4, duration: 2000, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ])
    ).start();

    scrollToBottom();
  }, []);

  const scrollToBottom = () => {
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, typing]);

  const handleSend = (text: string) => {
    const userMsg: Message = { id: `u-${Date.now()}`, text, from: 'user', ts: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setTyping(true);

    setTimeout(() => {
      const aiMsg: Message = {
        id: `ai-${Date.now()}`,
        text: getAIResponse(avatar.id),
        from: 'ai',
        ts: Date.now(),
      };
      setMessages((prev) => [...prev, aiMsg]);
      setTyping(false);
    }, 1400 + Math.random() * 600);
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />

      <LinearGradient
        colors={['#0A0C18', '#080910']}
        style={StyleSheet.absoluteFill}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 1 }}
      />

      {/* ── Header ── */}
      <Animated.View
        style={[
          styles.header,
          { paddingTop: insets.top + 10, opacity: headerFade, transform: [{ translateY: headerSlide }] },
        ]}
      >
        <Pressable style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>←</Text>
        </Pressable>

        {/* Avatar badge — the "hint" of the avatar */}
        <View style={styles.badgeArea}>
          {/* Outer glow ring */}
          <Animated.View
            style={[
              styles.badgeGlowRing,
              { backgroundColor: avatar.glowColor, opacity: badgeGlow },
            ]}
          />
          {/* Badge circle */}
          <Animated.View style={{ transform: [{ scale: badgePulse }] }}>
            <LinearGradient
              colors={[avatar.glowColor, avatar.primaryColor]}
              style={styles.badge}
              start={{ x: 0.3, y: 0 }}
              end={{ x: 0.7, y: 1 }}
            >
              {/* Mini face */}
              <LinearGradient
                colors={['#FDDCB5', '#E8A97C']}
                style={styles.badgeFace}
                start={{ x: 0.3, y: 0 }}
                end={{ x: 0.7, y: 1 }}
              >
                <Text style={styles.badgeEmoji}>{avatar.emoji}</Text>
              </LinearGradient>
              {/* Rim lights */}
              <View style={[styles.badgeRimL, { backgroundColor: avatar.accentColor }]} />
              <View style={[styles.badgeRimR, { backgroundColor: avatar.glowColor }]} />
            </LinearGradient>
          </Animated.View>

          {/* Active dot */}
          <View style={[styles.activeDot, { backgroundColor: '#22C55E' }]} />
        </View>

        {/* Name + status */}
        <View style={styles.headerMeta}>
          <Text style={[styles.headerName, { color: avatar.accentColor }]}>{avatar.name}</Text>
          <Text style={styles.headerStatus}>Active now</Text>
        </View>

        {/* Options placeholder */}
        <Pressable style={styles.optionsBtn}>
          <Text style={styles.optionsText}>···</Text>
        </Pressable>
      </Animated.View>

      {/* Header border */}
      <View style={[styles.headerBorder, { backgroundColor: avatar.primaryColor + '22' }]} />

      {/* ── Messages ── */}
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={insets.bottom}
      >
        <ScrollView
          ref={scrollRef}
          style={styles.messageList}
          contentContainerStyle={styles.messageContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Date separator */}
          <View style={styles.dateSep}>
            <View style={styles.dateLine} />
            <Text style={styles.dateText}>Today</Text>
            <View style={styles.dateLine} />
          </View>

          {messages.map((msg) => (
            <ChatBubble key={msg.id} message={msg} avatar={avatar} />
          ))}
          {typing && <TypingIndicator avatar={avatar} />}
        </ScrollView>

        <ChatInput avatar={avatar} onSend={handleSend} disabled={typing} />
        <View style={{ height: insets.bottom }} />
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#080910',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingBottom: 12,
    gap: 10,
  },
  backBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backText: {
    color: '#9CA3AF',
    fontSize: 22,
    fontWeight: '300',
  },
  badgeArea: {
    position: 'relative',
  },
  badgeGlowRing: {
    position: 'absolute',
    width: 54,
    height: 54,
    borderRadius: 27,
    top: -6,
    left: -6,
    opacity: 0.3,
  },
  badge: {
    width: 42,
    height: 42,
    borderRadius: 21,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeFace: {
    width: '64%',
    height: '68%',
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeEmoji: {
    fontSize: 12,
    color: '#fff',
  },
  badgeRimL: {
    position: 'absolute',
    left: 0,
    top: 6,
    bottom: 6,
    width: 2.5,
    borderRadius: 2,
    opacity: 0.6,
  },
  badgeRimR: {
    position: 'absolute',
    right: 0,
    top: 6,
    bottom: 6,
    width: 2.5,
    borderRadius: 2,
    opacity: 0.5,
  },
  activeDot: {
    position: 'absolute',
    bottom: 1,
    right: 1,
    width: 11,
    height: 11,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#080910',
  },
  headerMeta: {
    flex: 1,
    gap: 1,
  },
  headerName: {
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  headerStatus: {
    fontSize: 12,
    color: '#6B7280',
  },
  optionsBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionsText: {
    color: '#6B7280',
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: 1,
  },
  headerBorder: {
    height: 1,
  },
  messageList: {
    flex: 1,
  },
  messageContent: {
    paddingTop: 12,
    paddingBottom: 8,
  },
  dateSep: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 24,
    marginBottom: 16,
    gap: 10,
  },
  dateLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#1F2230',
  },
  dateText: {
    color: '#4B5563',
    fontSize: 11,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
});
