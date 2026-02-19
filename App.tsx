import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import AvatarSelectScreen from './src/screens/AvatarSelectScreen';

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AvatarSelectScreen />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
