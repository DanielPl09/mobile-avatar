export interface Avatar {
  id: string;
  name: string;
  subtitle: string;
  emoji: string;
  primaryColor: string;
  glowColor: string;
  accentColor: string;
}

export const AVATARS: Avatar[] = [
  {
    id: 'aria',
    name: 'Aria',
    subtitle: 'Creative & Empathetic',
    emoji: '✦',
    primaryColor: '#7C5CE8',
    glowColor: '#9B7FFF',
    accentColor: '#C4B0FF',
  },
  {
    id: 'nova',
    name: 'Nova',
    subtitle: 'Sharp & Strategic',
    emoji: '◈',
    primaryColor: '#0EA5E9',
    glowColor: '#38C4FF',
    accentColor: '#BAE6FD',
  },
  {
    id: 'sol',
    name: 'Sol',
    subtitle: 'Warm & Grounded',
    emoji: '⬡',
    primaryColor: '#F97316',
    glowColor: '#FB923C',
    accentColor: '#FED7AA',
  },
  {
    id: 'echo',
    name: 'Echo',
    subtitle: 'Calm & Analytical',
    emoji: '◎',
    primaryColor: '#10B981',
    glowColor: '#34D399',
    accentColor: '#A7F3D0',
  },
  {
    id: 'zara',
    name: 'Zara',
    subtitle: 'Bold & Direct',
    emoji: '◆',
    primaryColor: '#EC4899',
    glowColor: '#F472B6',
    accentColor: '#FBCFE8',
  },
];
