import { useEffect, useState } from 'react';

/** Узкий экран (телефон в портрете): своя раскладка с выезжающим меню. */
export const PHONE_QUERY = '(max-width: 760px)';

export function usePhone() {
  const [phone, setPhone] = useState(() => typeof window !== 'undefined' && window.matchMedia(PHONE_QUERY).matches);
  useEffect(() => {
    const mq = window.matchMedia(PHONE_QUERY);
    const on = () => setPhone(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return phone;
}
