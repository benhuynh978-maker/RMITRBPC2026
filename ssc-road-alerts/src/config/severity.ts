import type { Severity } from '../models/roadAlert';
export const SEVERITY: Record<Severity, { label: string; color: string; background: string; rank: number; advice: string }> = {
  normal: { label: 'Bình thường', color: '#218264', background: '#e8f4ee', rank: 0, advice: 'Tiếp tục quan sát khi lưu thông.' },
  low: { label: 'Thấp', color: '#347dc1', background: '#ebf3fc', rank: 1, advice: 'Chú ý tình trạng mặt đường.' },
  medium: { label: 'Trung bình', color: '#a76a00', background: '#fff5db', rank: 2, advice: 'Giảm tốc độ và quan sát đoạn đường.' },
  high: { label: 'Cao', color: '#df671b', background: '#fff0e5', rank: 3, advice: 'Thận trọng; cân nhắc tuyến đường khác.' },
  critical: { label: 'Nghiêm trọng', color: '#d33c4c', background: '#fdecef', rank: 4, advice: 'Ưu tiên tránh đoạn đường và theo dõi thông báo chính thức.' },
};
export const SEVERITY_ORDER: Severity[] = ['critical','high','medium','low','normal'];
