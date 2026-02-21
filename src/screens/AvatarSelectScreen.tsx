import React, { useState, useRef } from 'react';
import {
  Animated,
  Dimensions,
  Pressable,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { AVATARS, Avatar } from '../data/avatars';
import { AvatarSelectNavProp } from '../types';
import HeroAvatar from '../components/HeroAvatar';
import AvatarCarousel from '../components/AvatarCarousel';

const { height: SCREEN_H } = Dimensions.get('window');

export default function AvatarSelectScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<AvatarSelectNavProp>();
  const [selected, setSelected] = useState<Avatar>(AVATARS[0]);
  const [displayedAvatar, setDisplayedAvatar] = useState<Avatar>(AVATARS[0]);

  // Crossfade for hero + name
  const fadeAnim = useRef(new Animated.Value(1)).current;
  // Ambient glow color follows displayedAvatar (in sync with crossfade)
  const glowColorRef = useRef(displayedAvatar.glowColor);

  const handleSelectAvatar = (avatar: Avatar) => {
    setSelected(avatar);
    Animated.timing(fadeAnim, {
      toValue: 0,
      duration: 180,
      useNativeDriver: true,
    }).start(() => {
      setDisplayedAvatar(avatar);
      glowColorRef.current = avatar.glowColor;
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 260,
        useNativeDriver: true,
      }).start();
    });
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />

      <LinearGradient
        colors={['#0D0F1E', '#0A0B14', '#080910']}
        style={StyleSheet.absoluteFill}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 1 }}
      />

      {/* Ambient glow synced to displayedAvatar (updates after crossfade) */}
      <View
        style={[
          styles.ambientGlow,
          {
            backgroundColor: displayedAvatar.glowColor,
            top: SCREEN_H * 0.12,
          },
        ]}
      />

      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 16 }]}>
        <Text style={styles.screenTitle}>Choose your guide</Text>
      </View>

      {/* Hero */}
      <View style={styles.heroZone}>
        <Animated.View style={[styles.nameBadge, { opacity: fadeAnim }]}>
          <Text style={[styles.avatarName, { color: displayedAvatar.accentColor }]}>
            {displayedAvatar.name}
          </Text>
          <Text style={styles.avatarSubtitle}>{displayedAvatar.subtitle}</Text>
        </Animated.View>

        <Animated.View style={{ opacity: fadeAnim }}>
          <HeroAvatar avatar={displayedAvatar} />
        </Animated.View>
      </View>

      {/* Carousel */}
      <View style={styles.carouselZone}>
        <AvatarCarousel
          avatars={AVATARS}
          selectedId={selected.id}
          onSelect={handleSelectAvatar}
        />
      </View>

      {/* CTA */}
      <View style={[styles.ctaZone, { paddingBottom: insets.bottom + 24 }]}>
        <Pressable
          style={({ pressed }) => [
            styles.ctaButton,
            { shadowColor: displayedAvatar.glowColor },
            pressed && styles.ctaButtonPressed,
          ]}
          onPress={() => navigation.navigate('Hybrid', { avatar: displayedAvatar })}
        >
          <LinearGradient
            colors={[displayedAvatar.glowColor, displayedAvatar.primaryColor]}
            style={styles.ctaGradient}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
          >
            <Text style={styles.ctaLabel}>Select Persona</Text>
            <Text style={styles.ctaArrow}>→</Text>
          </LinearGradient>
        </Pressable>

        <Text style={styles.ctaHint}>You can switch personas anytime</Text>
      </View>
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
    width: 320,
    height: 320,
    borderRadius: 160,
    opacity: 0.08,
  },
  header: {
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  screenTitle: {
    fontSize: 13,
    fontWeight: '500',
    color: '#6B7280',
    letterSpacing: 2,
    textTransform: 'uppercase',
  },
  heroZone: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  nameBadge: {
    alignItems: 'center',
    gap: 4,
  },
  avatarName: {
    fontSize: 28,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  avatarSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    fontWeight: '400',
    letterSpacing: 0.3,
  },
  carouselZone: {
    paddingVertical: 20,
  },
  ctaZone: {
    paddingHorizontal: 28,
    alignItems: 'center',
    gap: 12,
  },
  ctaButton: {
    width: '100%',
    borderRadius: 50,
    overflow: 'hidden',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.45,
    shadowRadius: 18,
    elevation: 10,
  },
  ctaButtonPressed: {
    opacity: 0.88,
    transform: [{ scale: 0.97 }],
  },
  ctaGradient: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 18,
    paddingHorizontal: 32,
    gap: 10,
  },
  ctaLabel: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  ctaArrow: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
  },
  ctaHint: {
    color: '#4B5563',
    fontSize: 12,
    letterSpacing: 0.2,
  },
});
