import { X } from "lucide-react";
import type { ApiError } from "../api/types";
import type { Language, Translation } from "../i18n";
import { translateSuggestedCheck, translations } from "../i18n";

type Props = {
  error: ApiError;
  onClose: () => void;
  language?: Language;
  t?: Translation;
};

export function FailureModal({ error, onClose, language = "zh", t = translations[language] }: Props) {
  return (
    <div className="modalBackdrop" role="dialog" aria-modal="true" aria-labelledby="failure-title">
      <section className="modal">
        <header className="modalHeader">
          <div>
            <h2 id="failure-title">{t.modal.title}</h2>
            <p className="muted">{error.message}</p>
          </div>
          <button type="button" className="iconButton" onClick={onClose} aria-label={t.modal.close}>
            <X size={18} />
          </button>
        </header>

        <div className="modalBody">
          {error.operation ? (
            <p className="detailLine">
              <span className="detailLabel">{t.modal.operation}</span>
              <span>{error.operation}</span>
            </p>
          ) : null}

          {error.hermes_output ? (
            <section className="stack">
              <h3>{t.modal.hermesOutput}</h3>
              <pre>{error.hermes_output}</pre>
            </section>
          ) : null}

          {error.suggested_checks.length > 0 ? (
            <section className="stack">
              <h3>{t.modal.suggestedChecks}</h3>
              <ul className="checkList">
                {error.suggested_checks.map((check) => (
                  <li key={check}>{translateSuggestedCheck(check, language)}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      </section>
    </div>
  );
}
