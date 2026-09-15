from __future__ import annotations

from collections.abc import Sequence

from packages.services.src.domain.license import LicenseGrant


class LicenseMatrix:
    """Resolve a messy license string to one known policy entry.

    Sources report licenses inconsistently: SPDX identifiers, SPDX identifiers
    with different casing, human phrases, or an empty field. The matrix maps the
    variants it recognises onto a canonical identifier and returns ``None`` for
    everything else. ``None`` means "not provable", never "probably fine".
    """

    ALIASES: tuple[tuple[str, str], ...] = (
        ('cc0', 'CC0-1.0'),
        ('cc0 1.0', 'CC0-1.0'),
        ('cc zero', 'CC0-1.0'),
        ('cc-0', 'CC0-1.0'),
        ('creative commons zero', 'CC0-1.0'),
        ('public domain', 'CC0-1.0'),
        ('publicdomain', 'CC0-1.0'),
        ('unlicense', 'Unlicense'),
        ('the unlicense', 'Unlicense'),
        ('0bsd', '0BSD'),
        ('zero-clause bsd', '0BSD'),
        ('mit', 'MIT'),
        ('mit license', 'MIT'),
        ('expat', 'MIT'),
        ('isc', 'ISC'),
        ('isc license', 'ISC'),
        ('bsd', 'BSD-2-Clause'),
        ('bsd-2', 'BSD-2-Clause'),
        ('bsd 2-clause', 'BSD-2-Clause'),
        ('bsd-2-clause', 'BSD-2-Clause'),
        ('bsd-3', 'BSD-3-Clause'),
        ('bsd 3-clause', 'BSD-3-Clause'),
        ('bsd-3-clause', 'BSD-3-Clause'),
        ('apache', 'Apache-2.0'),
        ('apache 2', 'Apache-2.0'),
        ('apache 2.0', 'Apache-2.0'),
        ('apache-2', 'Apache-2.0'),
        ('apache license 2.0', 'Apache-2.0'),
        ('mpl-2.0', 'MPL-2.0'),
        ('mpl 2.0', 'MPL-2.0'),
        ('mozilla public license 2.0', 'MPL-2.0'),
        ('cc-by', 'CC-BY-4.0'),
        ('cc by', 'CC-BY-4.0'),
        ('cc by 4.0', 'CC-BY-4.0'),
        ('cc-by-sa', 'CC-BY-SA-4.0'),
        ('cc by-sa', 'CC-BY-SA-4.0'),
        ('cc by-sa 4.0', 'CC-BY-SA-4.0'),
        ('cc-by-nd', 'CC-BY-ND-4.0'),
        ('cc by-nd', 'CC-BY-ND-4.0'),
        ('cc by-nd 4.0', 'CC-BY-ND-4.0'),
        ('cc-by-nc', 'CC-BY-NC-4.0'),
        ('cc by-nc', 'CC-BY-NC-4.0'),
        ('cc by-nc 4.0', 'CC-BY-NC-4.0'),
        ('cc-by-nc-sa', 'CC-BY-NC-SA-4.0'),
        ('cc by-nc-sa', 'CC-BY-NC-SA-4.0'),
        ('cc-by-nc-nd', 'CC-BY-NC-ND-4.0'),
        ('cc by-nc-nd', 'CC-BY-NC-ND-4.0'),
        ('gplv2', 'GPL-2.0-only'),
        ('gpl-2.0', 'GPL-2.0-only'),
        ('gpl 2.0', 'GPL-2.0-only'),
        ('gplv3', 'GPL-3.0-only'),
        ('gpl-3.0', 'GPL-3.0-only'),
        ('gpl 3.0', 'GPL-3.0-only'),
        ('agplv3', 'AGPL-3.0-only'),
        ('agpl-3.0', 'AGPL-3.0-only'),
        ('agpl 3.0', 'AGPL-3.0-only'),
        ('lgplv3', 'LGPL-3.0-only'),
        ('lgpl-3.0', 'LGPL-3.0-only'),
        ('lgpl 3.0', 'LGPL-3.0-only'),
    )

    def __init__(self, grants: Sequence[LicenseGrant]) -> None:
        self._by_id: dict[str, LicenseGrant] = {grant.license_id: grant for grant in grants}
        self._by_lower_id: dict[str, LicenseGrant] = {
            grant.license_id.lower(): grant for grant in grants
        }
        self._aliases: dict[str, str] = dict(self.ALIASES)

    def resolve(self, raw_license: str | None) -> LicenseGrant | None:
        if raw_license is None:
            return None
        normalized = self._normalize(raw_license)
        if not normalized:
            return None
        canonical = self._aliases.get(normalized)
        if canonical is not None:
            return self._by_id.get(canonical)
        exact = self._by_id.get(raw_license)
        if exact is not None:
            return exact
        return self._by_lower_id.get(normalized)

    def known_license_ids(self) -> tuple[str, ...]:
        return tuple(self._by_id.keys())

    @staticmethod
    def _normalize(raw_license: str) -> str:
        collapsed = ' '.join(raw_license.split())
        return collapsed.strip(' "\'').lower()
