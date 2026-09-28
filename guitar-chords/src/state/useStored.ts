import { useEffect, useState } from 'react';

// Состояние, сохраняемое между запусками (localStorage в Electron хранится в профиле приложения).
export function useStored<T>(key: string, initial: T): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw == null) return initial;
      const parsed = JSON.parse(raw) as T;
      // Для объектов-настроек подмешиваем новые поля, появившиеся в новых версиях.
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed) && initial && typeof initial === 'object') {
        return { ...initial, ...parsed };
      }
      return parsed;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // хранилище недоступно — работаем без сохранения
    }
  }, [key, value]);

  return [value, setValue];
}
