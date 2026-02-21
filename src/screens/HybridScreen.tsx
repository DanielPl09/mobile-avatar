import React, { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Dimensions,
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
import HeroAvatar from '../components/HeroAvatar';
import ChatBubble, { TypingIndicator } from '../components/ChatBubble';
import ChatInput from '../components/ChatInput';
import { HybridNavProp, HybridRouteProp, Message } from '../types';
import { GREETINGS, getAIResponse } from '../data/mockResponses';

const { height: SCREEN_H } = Dimensions.get('window');
const AVATAR_ZONE_H = SCREEN_H * 0.42;

export default function HybridScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<HybridNavProp>();
  const { params } = useRoute<HybridRouteProp>();
  const { avatar } = params;

  const [messages, setMessages] = useState<Message[]>([]);
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  // Entrance animations
  const avatarSlide = useRef(new Animated.Value(30)).current;
  const avatarFade = useRef(new Animated.Value(0)).current;
  const chatSlide = useRef(new Animated.Value(40)).current;
  const chatFade = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Avatar slides in
    Animated.parallel([
      Animated.timing(avatarFade, { toValue: 1, duration: 500, delay: 100, useNativeDriver: true }),
      Animated.timing(avatarSlide, { toValue: 0, duration: 450, delay: 100, useNativeDriver: true }),
    ]).start();

    // Chat panel fades in slightly after
    Animated.parallel([
      Animated.timing(chatFade, { toValue: 1, duration: 400, delay: 350, useNativeDriver: true }),
      Animated.timing(chatSlide, { toValue: 0, duration: 380, delay: 350, useNativeDriver: true }),
    ]).start();

    // Greeting message appears after entrance
    const greetTimer = setTimeout(() => {
      const greeting: Message = {
        id: 'greeting',
        text: GREETINGS[avatar.id] ?? GREETINGS.aria,
        from: 'ai',
        ts: Date.now(),
      };
      setMessages([greeting]);
    }, 700);

    return () => clearTimeout(greetTimer);
  }, []);

  const scrollToBottom = () => {
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80);
  };

  useEffect(() => {
    if (messages.length > 0) scrollToBottom();
  }, [messages, typing]);

  const handleSend = (text: string) => {
    const userMsg: Message = { id: `u-${Date.now()}`, text, from: 'user', ts: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setTyping(true);

    // Simulate AI response then transition to FullChat
    setTimeout(() => {
      const aiMsg: Message = {
        id: `ai-${Date.now()}`,
        text: getAIResponse(avatar.id),
        from: 'ai',
        ts: Date.now(),
      };
      setMessages((prev) => {
        const updated = [...prev, aiMsg];
        // Transition to FullChat after first exchange
        setTimeout(() => {
          navigation.replace('FullChat', { avatar, initialMessages: updated });
        }, 900);
        return updated;
      });
      setTyping(false);
    }, 1600);
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />

      {/* Background */}
      <LinearGradient
        colors={['#0D0F1E', '#0A0B14', '#080910']}
        style={StyleSheet.absoluteFill}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 1 }}
      />

      {/* Ambient glow behind avatar */}
      <View style={[styles.ambientGlow, { backgroundColor: avatar.glowColor }]} />

      {/* Back button */}
      <Pressable
        style={[styles.backBtn, { top: insets.top + 14 }]}
        onPress={() => navigation.goBack()}
      >
        <Text style={styles.backText}>←</Text>
      </Pressable>

      {/* Avatar zone */}
      <Animated.View
        style={[
          styles.avatarZone,
          { opacity: avatarFade, transform: [{ translateY: avatarSlide }] },
        ]}
      >
        {/* Avatar name chip */}
        <View style={[styles.namePill, { borderColor: avatar.primaryColor + '55' }]}>
          <View style={[styles.activeDot, { backgroundColor: avatar.glowColor }]} />
          <Text style={[styles.nameText, { color: avatar.accentColor }]}>{avatar.name}</Text>
        </View>

        {/* Compact hero avatar — scale down via wrapper */}
        <View style={styles.avatarScale}>
          <HeroAvatar avatar={avatar} />
        </View>
      </Animated.View>

      {/* Gradient fade from avatar zone into chat zone */}
      <LinearGradient
        colors={['transparent', '#080910CC', '#080910']}
        style={styles.fadeOverlay}
        pointerEvents="none"
      />

      {/* Chat float panel */}
      <Animated.View
        style={[
          styles.chatPanel,
          { opacity: chatFade, transform: [{ translateY: chatSlide }] },
        ]}
      >
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
            {messages.map((msg, i) => (
              <ChatBubble key={msg.id} message={msg} avatar={avatar} delay={i === 0 ? 0 : 0} />
            ))}
            {typing && <TypingIndicator avatar={avatar} />}
          </ScrollView>

          {messages.length > 0 && !typing && (
            <ChatInput
              avatar={avatar}
              onSend={handleSend}
              disabled={typing}
              placeholder={`Reply to ${avatar.name}...`}
            />
          )}

          {/* Transition hint */}
          {messages.length === 0 && (
            <View style={[styles.hintBar, { paddingBottom: insets.bottom + 8 }]}>
              <Text style={styles.hintText}>↑ Waiting for {avatar.name}...</Text>
            </View>
          )}
        </KeyboardAvoidingView>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#080910',
  },
  ambientGlow: {
    position: 'absolute',
    alignSelf: 'center',
    top: 20,
    width: 280,
    height: 280,
    borderRadius: 140,
    opacity: 0.07,
  },
  backBtn: {
    position: 'absolute',
    left: 20,
    zIndex: 10,
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backText: {
    color: '#9CA3AF',
    fontSize: 22,
    fontWeight: '300',
  },
  avatarZone: {
    height: AVATAR_ZONE_H,
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingBottom: 8,
  },
  namePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 5,
    marginBottom: 12,
    backgroundColor: '#12141F88',
  },
  activeDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  nameText: {
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
  avatarScale: {
    transform: [{ scale: 0.72 }],
    marginBottom: -18,
  },
  fadeOverlay: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: AVATAR_ZONE_H - 60,
    height: 100,
    zIndex: 1,
  },
  chatPanel: {
    flex: 1,
    zIndex: 2,
  },
  messageList: {
    flex: 1,
  },
  messageContent: {
    paddingTop: 8,
    paddingBottom: 12,
  },
  hintBar: {
    alignItems: 'center',
    paddingTop: 16,
    paddingBottom: 24,
  },
  hintText: {
    color: '#374151',
    fontSize: 13,
    letterSpacing: 0.3,
  },
});
