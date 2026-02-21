import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Avatar } from '../data/avatars';
import { Message } from '../types';

interface ChatBubbleProps {
  message: Message;
  avatar: Avatar;
  /** Delay before entrance animation fires (ms) */
  delay?: number;
}

export default function ChatBubble({ message, avatar, delay = 0 }: ChatBubbleProps) {
  const slideAnim = useRef(new Animated.Value(18)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 320,
        delay,
        useNativeDriver: true,
      }),
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 280,
        delay,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  const isAI = message.from === 'ai';

  return (
    <Animated.View
      style={[
        styles.row,
        isAI ? styles.rowAI : styles.rowUser,
        { opacity: fadeAnim, transform: [{ translateY: slideAnim }] },
      ]}
    >
      {isAI ? (
        <View
          style={[
            styles.bubble,
            styles.bubbleAI,
            { borderColor: avatar.primaryColor + '55' },
          ]}
        >
          {/* Subtle left accent strip */}
          <View style={[styles.aiAccent, { backgroundColor: avatar.glowColor }]} />
          <Text style={styles.textAI}>{message.text}</Text>
        </View>
      ) : (
        <LinearGradient
          colors={[avatar.glowColor, avatar.primaryColor]}
          style={[styles.bubble, styles.bubbleUser]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        >
          <Text style={styles.textUser}>{message.text}</Text>
        </LinearGradient>
      )}
    </Animated.View>
  );
}

/** Three animated dots for AI typing indicator */
export function TypingIndicator({ avatar }: { avatar: Avatar }) {
  const dots = [
    useRef(new Animated.Value(0)).current,
    useRef(new Animated.Value(0)).current,
    useRef(new Animated.Value(0)).current,
  ];

  useEffect(() => {
    const anims = dots.map((dot, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 160),
          Animated.timing(dot, { toValue: 1, duration: 300, useNativeDriver: true }),
          Animated.timing(dot, { toValue: 0, duration: 300, useNativeDriver: true }),
          Animated.delay((2 - i) * 160),
        ])
      )
    );
    anims.forEach((a) => a.start());
    return () => anims.forEach((a) => a.stop());
  }, []);

  return (
    <View style={[styles.row, styles.rowAI]}>
      <View style={[styles.bubble, styles.bubbleAI, styles.typingBubble, { borderColor: avatar.primaryColor + '55' }]}>
        <View style={[styles.aiAccent, { backgroundColor: avatar.glowColor }]} />
        <View style={styles.dotsRow}>
          {dots.map((dot, i) => (
            <Animated.View
              key={i}
              style={[
                styles.dot,
                { backgroundColor: avatar.accentColor, opacity: dot,
                  transform: [{ scale: dot.interpolate({ inputRange: [0, 1], outputRange: [0.7, 1.2] }) }] },
              ]}
            />
          ))}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    marginVertical: 4,
    paddingHorizontal: 16,
  },
  rowAI: {
    alignItems: 'flex-start',
  },
  rowUser: {
    alignItems: 'flex-end',
  },
  bubble: {
    maxWidth: '78%',
    borderRadius: 18,
    paddingVertical: 12,
    paddingHorizontal: 16,
    overflow: 'hidden',
  },
  bubbleAI: {
    backgroundColor: '#12141F',
    borderWidth: 1,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    paddingLeft: 20,
  },
  aiAccent: {
    position: 'absolute',
    left: 0,
    top: 10,
    bottom: 10,
    width: 3,
    borderRadius: 2,
  },
  bubbleUser: {
    borderRadius: 18,
  },
  textAI: {
    color: '#E5E7EB',
    fontSize: 15,
    lineHeight: 22,
    flexShrink: 1,
  },
  textUser: {
    color: '#FFFFFF',
    fontSize: 15,
    lineHeight: 22,
    fontWeight: '500',
  },
  typingBubble: {
    paddingVertical: 14,
  },
  dotsRow: {
    flexDirection: 'row',
    gap: 5,
    alignItems: 'center',
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
});
