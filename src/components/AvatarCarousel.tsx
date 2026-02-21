import React, { useRef } from 'react';
import {
  Animated,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Avatar } from '../data/avatars';

const ITEM_SIZE = 64;
const ITEM_SIZE_ACTIVE = 92;
const ITEM_MARGIN = 10;

interface AvatarCarouselProps {
  avatars: Avatar[];
  selectedId: string;
  onSelect: (avatar: Avatar) => void;
}

export default function AvatarCarousel({
  avatars,
  selectedId,
  onSelect,
}: AvatarCarouselProps) {
  // One Animated.Value per item for smooth scale/opacity transitions
  const animations = useRef(
    avatars.reduce<Record<string, Animated.Value>>((acc, a) => {
      acc[a.id] = new Animated.Value(a.id === selectedId ? 1 : 0);
      return acc;
    }, {})
  ).current;

  const handleSelect = (avatar: Avatar) => {
    if (avatar.id === selectedId) return;

    // Deselect old
    Animated.timing(animations[selectedId], {
      toValue: 0,
      duration: 220,
      useNativeDriver: false,
    }).start();

    // Select new
    Animated.timing(animations[avatar.id], {
      toValue: 1,
      duration: 220,
      useNativeDriver: false,
    }).start();

    onSelect(avatar);
  };

  return (
    <View style={styles.wrapper}>
      <FlatList
        data={avatars}
        keyExtractor={(item) => item.id}
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => {
          const anim = animations[item.id];
          const isSelected = item.id === selectedId;

          const size = anim.interpolate({
            inputRange: [0, 1],
            outputRange: [ITEM_SIZE, ITEM_SIZE_ACTIVE],
          });
          const opacity = anim.interpolate({
            inputRange: [0, 1],
            outputRange: [0.45, 1],
          });
          const borderWidth = anim.interpolate({
            inputRange: [0, 1],
            outputRange: [0, 2.5],
          });
          const glowOpacity = anim.interpolate({
            inputRange: [0, 1],
            outputRange: [0, 0.55],
          });

          return (
            <Pressable onPress={() => handleSelect(item)} style={styles.item}>
              {/* Outer glow behind selected */}
              <Animated.View
                style={[
                  styles.glowRing,
                  {
                    width: ITEM_SIZE_ACTIVE + 24,
                    height: ITEM_SIZE_ACTIVE + 24,
                    borderRadius: (ITEM_SIZE_ACTIVE + 24) / 2,
                    backgroundColor: item.glowColor,
                    opacity: glowOpacity,
                  },
                ]}
              />

              {/* Avatar circle */}
              <Animated.View
                style={[
                  styles.avatarCircleWrapper,
                  {
                    width: size,
                    height: size,
                    borderRadius: Animated.divide(size, 2) as any,
                    borderColor: item.glowColor,
                    borderWidth,
                    opacity,
                  },
                ]}
              >
                <LinearGradient
                  colors={[item.glowColor, item.primaryColor]}
                  style={StyleSheet.absoluteFill}
                  start={{ x: 0.3, y: 0 }}
                  end={{ x: 0.7, y: 1 }}
                />
                {/* Skin face */}
                <View style={styles.faceInner}>
                  <LinearGradient
                    colors={['#FDDCB5', '#E8A97C']}
                    style={styles.skinGrad}
                    start={{ x: 0.3, y: 0 }}
                    end={{ x: 0.7, y: 1 }}
                  >
                    <Text style={styles.itemEmoji}>{item.emoji}</Text>
                  </LinearGradient>
                </View>
              </Animated.View>

              {/* Name label — only under selected */}
              {isSelected && (
                <Text style={[styles.label, { color: item.accentColor }]}>
                  {item.name}
                </Text>
              )}
            </Pressable>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    alignItems: 'center',
  },
  list: {
    paddingHorizontal: 24,
    alignItems: 'center',
  },
  item: {
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: ITEM_MARGIN,
    height: ITEM_SIZE_ACTIVE + 40,
  },
  glowRing: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    marginTop: -(ITEM_SIZE_ACTIVE + 24) / 2,
    marginLeft: -(ITEM_SIZE_ACTIVE + 24) / 2,
  },
  avatarCircleWrapper: {
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  faceInner: {
    width: '65%',
    height: '65%',
    borderRadius: 999,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  skinGrad: {
    flex: 1,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemEmoji: {
    fontSize: 18,
    color: '#fff',
    textShadowColor: 'rgba(255,255,255,0.9)',
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 6,
  },
  label: {
    marginTop: 6,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
});
