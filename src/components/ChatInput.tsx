import React, { useState } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Avatar } from '../data/avatars';

interface ChatInputProps {
  avatar: Avatar;
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({
  avatar,
  onSend,
  disabled = false,
  placeholder = 'Message...',
}: ChatInputProps) {
  const [text, setText] = useState('');

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
  };

  const canSend = text.trim().length > 0 && !disabled;

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder={placeholder}
          placeholderTextColor="#4B5563"
          onSubmitEditing={handleSend}
          returnKeyType="send"
          editable={!disabled}
          multiline={false}
        />
        <Pressable
          style={[
            styles.sendBtn,
            { backgroundColor: canSend ? avatar.primaryColor : '#1F2230' },
          ]}
          onPress={handleSend}
          disabled={!canSend}
        >
          <Text style={[styles.sendIcon, { opacity: canSend ? 1 : 0.35 }]}>↑</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#080910',
    borderTopWidth: 1,
    borderTopColor: '#1A1D2E',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#12141F',
    borderRadius: 28,
    paddingHorizontal: 4,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: '#1F2230',
  },
  input: {
    flex: 1,
    color: '#F3F4F6',
    fontSize: 15,
    paddingHorizontal: 16,
    paddingVertical: 10,
    maxHeight: 100,
  },
  sendBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 2,
  },
  sendIcon: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
  },
});
