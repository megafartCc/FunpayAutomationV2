import React from "react";

import { useI18n } from "../../i18n/useI18n";

type StratzGameHistoryPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const StratzGameHistoryPage: React.FC<StratzGameHistoryPageProps> = () => {
  const { t } = useI18n();

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm">
      <div className="text-lg font-semibold text-neutral-900">{t("title.stratzHistory")}</div>
    </div>
  );
};

export default StratzGameHistoryPage;
