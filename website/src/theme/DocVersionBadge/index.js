// The release a doc page is "as of" (tools/gen_page_versions.py: the earliest release whose text of the page is still
// its text), quietly at the right of the title row. Pages without one (generated at build time) show nothing.
import React from 'react';
import clsx from 'clsx';
import {ThemeClassNames} from '@docusaurus/theme-common';
import {useDoc, useDocsVersion} from '@docusaurus/plugin-content-docs/client';
import pageVersions from '@site/src/data/page_versions.json';

export default function DocVersionBadge({className}) {
  const version = useDocsVersion();
  const {metadata} = useDoc();
  // source: "@site/../docs/<path>" (current) or "@site/versioned_docs/version-<v>/<path>"
  const m = metadata.source.match(/(?:\/docs\/|\/versioned_docs\/version-[^/]+\/)(.+)$/);
  const key = version.version === 'current' ? 'current' : version.version;
  const asOf = m && (pageVersions[key] || {})[m[1]];
  if (!asOf) return null;
  return (
    <span className={clsx(className, ThemeClassNames.docs.docVersionBadge, 'pm-version-note')}>as of {asOf}</span>
  );
}
