// The release a doc page is "as of" (tools/gen_page_versions.py: the earliest release whose text of the page is still
// its text), quietly at the right of the title row. Looked up by the page's URL path, so it works on pages without a
// doc of their own (generated category indexes); pages without an entry show nothing.
import React from 'react';
import clsx from 'clsx';
import {useLocation} from '@docusaurus/router';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {ThemeClassNames} from '@docusaurus/theme-common';
import {useDocsVersion} from '@docusaurus/plugin-content-docs/client';
import pageVersions from '@site/src/data/page_versions.json';

export default function DocVersionBadge({className}) {
  const version = useDocsVersion();
  const {pathname} = useLocation();
  const {siteConfig} = useDocusaurusContext();
  const key = version.version === 'current' ? 'current' : version.version;
  // strip the base URL and the version's path prefix (docusaurus.config.js: the current docs under "next/", the latest
  // release at the root, older ones under their number)
  let rel = pathname.slice(siteConfig.baseUrl.length).replace(/\/$/, '');
  const prefix = version.version === 'current' ? 'next' : version.isLast ? '' : version.version;
  if (prefix && (rel === prefix || rel.startsWith(prefix + '/'))) rel = rel.slice(prefix.length).replace(/^\//, '');
  const asOf = (pageVersions[key] || {})[rel];
  if (!asOf) return null;
  return (
    <span className={clsx(className, ThemeClassNames.docs.docVersionBadge, 'pm-version-note')}>as of {asOf}</span>
  );
}
