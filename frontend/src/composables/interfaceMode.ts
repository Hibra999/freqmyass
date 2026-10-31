const interfaceMode = useLocalStorage<'guided' | 'native'>('freqmyass-interface', 'guided');

export function useInterfaceMode() {
  return interfaceMode;
}
