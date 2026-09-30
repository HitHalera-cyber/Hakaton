export {};

declare global {
  interface UpdateStatus {
    state: 'checking' | 'available' | 'none' | 'downloading' | 'downloaded' | 'error' | 'unsupported';
    version?: string;
    percent?: number;
    message?: string;
  }

  interface AppInfo {
    version: string;
    portable: boolean;
    updatesSupported: boolean;
    releasesUrl: string;
  }

  interface Window {
    /** Мост из electron/preload.cjs (нет в браузерном режиме разработки). */
    gc?: {
      info(): Promise<AppInfo>;
      checkUpdates(): Promise<void>;
      downloadUpdate(): Promise<void>;
      installUpdate(): Promise<void>;
      openReleases(): Promise<void>;
      onUpdate(cb: (s: UpdateStatus) => void): () => void;
      /** Сохранить текущую страницу (печатную версию) в PDF. true — файл сохранён. */
      printToPdf?(name: string): Promise<boolean>;
    };
  }
}
