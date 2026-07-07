import React from 'react';
import NotFoundContent from '@theme-original/NotFound/Content';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';
import versions from '@site/versions.json';

// The latest released snapshot serves at the site root, so its
// version-prefixed URLs (/<latest>/SPEC, ...) don't exist until the next
// release demotes it to an archived path — yet release notes want to link
// the pinned form from day one. GitHub Pages serves this 404 page for any
// unknown path; when the path is just the latest version's prefix, forward
// to the same page at the root instead of dead-ending. Anything else falls
// through to the real 404.
export default function NotFoundContentWrapper(props) {
  const {siteConfig} = useDocusaurusContext();
  const latest = versions[0];
  if (ExecutionEnvironment.canUseDOM && latest) {
    const prefix = `${siteConfig.baseUrl}${latest}`;
    const {pathname, search, hash} = window.location;
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) {
      const rest = pathname.slice(prefix.length).replace(/^\//, '');
      window.location.replace(`${siteConfig.baseUrl}${rest}${search}${hash}`);
      return null;
    }
  }
  return <NotFoundContent {...props} />;
}
