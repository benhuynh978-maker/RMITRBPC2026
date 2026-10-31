import { Clock3 } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';

/** Small pill label. variant: neutral | teal | accent */
export function Badge({ variant = 'neutral', icon: Icon, children, className = '', ...rest }) {
  return (
    <span className={`badge badge--${variant} ${className}`.trim()} {...rest}>
      {Icon && <Icon size={14} aria-hidden="true" />}
      {children}
    </span>
  );
}

/** "Sắp ra mắt / Coming soon" pill used on every UI-only widget. */
export function ComingSoon({ className = '' }) {
  const { t } = useI18n();
  return (
    <Badge variant="accent" icon={Clock3} className={className}>
      {t('common.comingSoon')}
    </Badge>
  );
}

