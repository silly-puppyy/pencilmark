// The version a doc page belongs to, quietly: "as of 1.2" in low contrast at the right of the title row (the stock
// badge sits above the title as a coloured chip, which pulls the eye on every page).
import React from 'react';
import clsx from 'clsx';
import {ThemeClassNames} from '@docusaurus/theme-common';
import {useDocsVersion} from '@docusaurus/plugin-content-docs/client';

export default function DocVersionBadge({className}) {
  const version = useDocsVersion();
  if (!version.badge) return null;
  return (
    <span className={clsx(className, ThemeClassNames.docs.docVersionBadge, 'pm-version-note')}>
      as of {version.label}
    </span>
  );
}
