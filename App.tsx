import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import AvatarSelectScreen from './src/screens/AvatarSelectScreen';
import HybridScreen from './src/screens/HybridScreen';
import FullChatScreen from './src/screens/FullChatScreen';
import { RootStackParamList } from './src/types';

const Stack = createStackNavigator<RootStackParamList>();

/** Avatar select → Hybrid: screen rises up from below */
function slideUpInterpolator({ current, layouts }: any) {
  return {
    cardStyle: {
      opacity: current.progress.interpolate({
        inputRange: [0, 0.6, 1],
        outputRange: [0, 0.8, 1],
      }),
      transform: [
        {
          translateY: current.progress.interpolate({
            inputRange: [0, 1],
            outputRange: [layouts.screen.height * 0.22, 0],
          }),
        },
      ],
    },
    overlayStyle: {
      opacity: current.progress.interpolate({
        inputRange: [0, 1],
        outputRange: [0, 0.5],
      }),
    },
  };
}

/** Hybrid → FullChat: subtle slide-up, chat expands in */
function chatExpandInterpolator({ current, layouts }: any) {
  return {
    cardStyle: {
      opacity: current.progress.interpolate({
        inputRange: [0, 0.5, 1],
        outputRange: [0, 0.9, 1],
      }),
      transform: [
        {
          translateY: current.progress.interpolate({
            inputRange: [0, 1],
            outputRange: [layouts.screen.height * 0.1, 0],
          }),
        },
      ],
    },
  };
}

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <NavigationContainer>
          <Stack.Navigator
            screenOptions={{
              headerShown: false,
              cardStyle: { backgroundColor: '#080910' },
              cardOverlayEnabled: true,
              presentation: 'card',
            }}
          >
            <Stack.Screen name="AvatarSelect" component={AvatarSelectScreen} />

            <Stack.Screen
              name="Hybrid"
              component={HybridScreen}
              options={{ cardStyleInterpolator: slideUpInterpolator }}
            />

            <Stack.Screen
              name="FullChat"
              component={FullChatScreen}
              options={{ cardStyleInterpolator: chatExpandInterpolator }}
            />
          </Stack.Navigator>
        </NavigationContainer>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
