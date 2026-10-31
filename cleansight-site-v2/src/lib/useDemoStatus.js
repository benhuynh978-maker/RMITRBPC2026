import { useEffect, useState } from 'react';
import { DEMO_HEALTH_INTERVAL_MS } from './config.js';
import { checkHealth, demoEnabled } from './demoApi.js';

/**
 * Trạng thái dịch vụ live demo: 'checking' | 'online' | 'offline'.
 * Kiểm tra khi mở trang, rồi mỗi 30 giây khi tab đang hiển thị. Trả [trạng thái, hàm đặt lại].
 */
export default function useDemoStatus() {
  const [service, setService] = useState(demoEnabled() ? 'checking' : 'offline');

  useEffect(() => {
    if (!demoEnabled()) return undefined;
    const controller = new AbortController();
    let timer;
    let running = false;
    const tick = async () => {
      if (running) return;
      running = true;
      if (document.visibilityState === 'visible') {
        const ok = await checkHealth(controller.signal);
        if (controller.signal.aborted) return;
        setService(ok ? 'online' : 'offline');
      }
      running = false;
      timer = setTimeout(tick, DEMO_HEALTH_INTERVAL_MS);
    };
    tick();
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        clearTimeout(timer);
        tick();
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []);

  return [service, setService];
}
