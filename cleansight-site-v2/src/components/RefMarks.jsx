import { useI18n } from '../i18n/I18nProvider.jsx';
import { revealTarget } from './ScrollManager.jsx';

/** Superscript citation links, e.g. [1] → #ref-1. Opens the collapsed reference list before jumping. */
export default function RefMarks({ refs }) {
  const { t } = useI18n();
  if (!refs || refs.length === 0) return null;
  return (
    <sup className="refmarks">
      {refs.map((n) => (
        <a
          key={n}
          href={`#ref-${n}`}
          aria-label={`${t('common.refLabel')} ${n}`}
          onClick={() => revealTarget(document.getElementById(`ref-${n}`))}
        >
          [{n}]
        </a>
      ))}
    </sup>
  );
}
