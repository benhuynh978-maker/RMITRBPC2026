import { useId, useState } from 'react';
import type { FormEvent } from 'react';

/** Hỏi khoá quản trị khi máy chủ trả 401. Khoá chỉ nằm trong state này và roiService (bộ nhớ), không lưu đâu khác. */
export function KeyForm({ onSubmit, onCancel }: { onSubmit: (key: string) => void; onCancel: () => void }) {
  const [key, setKey] = useState('');
  const id = useId();
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!key.trim()) return;
    const value = key;
    setKey('');
    onSubmit(value);
  }
  return <form className="roi-keyform" onSubmit={submit}>
    <label htmlFor={id}>The server requires an admin key. Enter the key (kept in page memory only, not stored)</label>
    <input id={id} type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} />
    <div className="roi-actions">
      <button type="submit" className="refresh" disabled={!key.trim()}>Use key and retry</button>
      <button type="button" className="secondary" onClick={onCancel}>Cancel</button>
    </div>
  </form>;
}
