/**
 * @file apps/referee-mobile/index.ts
 * @layer Mobile — Expo Bootstrap
 * @description Registers the referee mobile app root component for Expo Go and
 *              native builds.
 * @dependencies Expo registerRootComponent, App component
 */

import { registerRootComponent } from 'expo';

import App from './App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(App);
