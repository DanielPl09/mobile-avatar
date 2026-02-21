import { StackNavigationProp } from '@react-navigation/stack';
import { RouteProp } from '@react-navigation/native';
import { Avatar } from '../data/avatars';

export interface Message {
  id: string;
  text: string;
  from: 'user' | 'ai';
  ts: number;
}

export type RootStackParamList = {
  AvatarSelect: undefined;
  Hybrid: { avatar: Avatar };
  FullChat: { avatar: Avatar; initialMessages: Message[] };
};

export type AvatarSelectNavProp = StackNavigationProp<RootStackParamList, 'AvatarSelect'>;
export type HybridNavProp = StackNavigationProp<RootStackParamList, 'Hybrid'>;
export type HybridRouteProp = RouteProp<RootStackParamList, 'Hybrid'>;
export type FullChatNavProp = StackNavigationProp<RootStackParamList, 'FullChat'>;
export type FullChatRouteProp = RouteProp<RootStackParamList, 'FullChat'>;
