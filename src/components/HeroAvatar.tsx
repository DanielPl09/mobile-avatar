import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View, Text, Easing } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Avatar } from '../data/avatars';

interface HeroAvatarProps {
  avatar: Avatar;
}

export default function HeroAvatar({ avatar }: HeroAvatarProps) {
  const floatAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const glowAnim = useRef(new Animated.Value(0.6)).current;

  useEffect(() => {
    // Floating idle animation
    Animated.loop(
      Animated.sequence([
        Animated.timing(floatAnim, {
          toValue: -12,
          duration: 2200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(floatAnim, {
          toValue: 0,
          duration: 2200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ])
    ).start();

    // Subtle scale pulse
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.03,
          duration: 2800,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 2800,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ])
    ).start();

    // Glow pulse
    Animated.loop(
      Animated.sequence([
        Animated.timing(glowAnim, {
          toValue: 1,
          duration: 2000,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(glowAnim, {
          toValue: 0.6,
          duration: 2000,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, []);

  return (
    <Animated.View
      style={[
        styles.container,
        { transform: [{ translateY: floatAnim }, { scale: pulseAnim }] },
      ]}
    >
      {/* Outer radial glow ring */}
      <Animated.View
        style={[
          styles.outerGlow,
          {
            backgroundColor: avatar.glowColor,
            opacity: glowAnim,
            shadowColor: avatar.glowColor,
          },
        ]}
      />

      {/* Mid glow ring */}
      <View
        style={[
          styles.midGlow,
          { backgroundColor: avatar.primaryColor + '30' },
        ]}
      />

      {/* Avatar body */}
      <LinearGradient
        colors={[avatar.glowColor, avatar.primaryColor, '#0A0B14']}
        locations={[0, 0.5, 1]}
        style={styles.avatarBody}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 1 }}
      >
        {/* Inner face area */}
        <LinearGradient
          colors={['#FDDCB5', '#F4B97C', '#D4956A']}
          style={styles.face}
          start={{ x: 0.3, y: 0 }}
          end={{ x: 0.7, y: 1 }}
        >
          <Text style={styles.emojiGlyph}>{avatar.emoji}</Text>
        </LinearGradient>

        {/* Rim light left */}
        <View
          style={[styles.rimLeft, { backgroundColor: avatar.accentColor }]}
        />
        {/* Rim light right */}
        <View
          style={[styles.rimRight, { backgroundColor: avatar.glowColor }]}
        />
      </LinearGradient>

      {/* Ground reflection */}
      <LinearGradient
        colors={[avatar.primaryColor + '40', 'transparent']}
        style={styles.groundReflection}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 1 }}
      />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  outerGlow: {
    position: 'absolute',
    width: 260,
    height: 260,
    borderRadius: 130,
    opacity: 0.12,
    shadowOffset: { width: 0, height: 0 },
    shadowRadius: 60,
    shadowOpacity: 0.8,
  },
  midGlow: {
    position: 'absolute',
    width: 210,
    height: 210,
    borderRadius: 105,
  },
  avatarBody: {
    width: 180,
    height: 220,
    borderRadius: 90,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    position: 'relative',
  },
  face: {
    width: 110,
    height: 130,
    borderRadius: 55,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: -10,
  },
  emojiGlyph: {
    fontSize: 52,
    color: '#ffffff',
    textShadowColor: 'rgba(255,255,255,0.8)',
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 12,
  },
  rimLeft: {
    position: 'absolute',
    left: 0,
    top: 20,
    width: 6,
    height: 160,
    borderRadius: 3,
    opacity: 0.6,
  },
  rimRight: {
    position: 'absolute',
    right: 0,
    top: 20,
    width: 6,
    height: 160,
    borderRadius: 3,
    opacity: 0.5,
  },
  groundReflection: {
    width: 120,
    height: 20,
    borderRadius: 60,
    marginTop: -6,
    opacity: 0.5,
  },
});
