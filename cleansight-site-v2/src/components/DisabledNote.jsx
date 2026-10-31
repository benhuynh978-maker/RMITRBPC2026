import { Info } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';

/** Visible explanation for disabled controls; referenced via aria-describedby. */
export default function DisabledNote({ id, children }) {
  const { t } = useI18n();
  return (
    <p id={id} className="disabled-note">
      <Info size={16} aria-hidden="true" />
      <span>{children ?? t('common.disabledHint')}</span>
    </p>
  );
}
