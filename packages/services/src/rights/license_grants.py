from __future__ import annotations

from packages.services.src.domain.license import LicenseGrant, StorefrontListing
from packages.services.src.domain.rights import RightsAction

_ALL_ACTIONS: tuple[RightsAction, ...] = (
    RightsAction.RESELL,
    RightsAction.REDISTRIBUTE,
    RightsAction.MODIFY,
    RightsAction.SUBLICENSE,
)

_ATTRIBUTION: tuple[str, ...] = (
    'Credit the creator',
    'Link to the license text',
    'Indicate whether changes were made',
)


class DefaultLicenseGrants:
    """The platform's license policy table.

    Immutable by construction (a tuple of frozen records). Editing an entry
    changes what the storefront is allowed to sell, so a change here is a
    reviewed change, not a refactor.

    Two flags are deliberately independent: ``commercial_use_allowed`` says
    whether the license permits earning money, while ``storefront_listing`` says
    whether Velmor chooses to sell it. Copyleft licenses pass the first and fail
    the second, because a buyer free to redistribute what they paid for voids
    the price.
    """

    TABLE: tuple[LicenseGrant, ...] = (
        LicenseGrant(
            license_id='CC0-1.0',
            name='Creative Commons Zero v1.0 Universal',
            granted_actions=_ALL_ACTIONS,
            obligations=(),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='Unlicense',
            name='The Unlicense',
            granted_actions=_ALL_ACTIONS,
            obligations=(),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='0BSD',
            name='BSD Zero Clause License',
            granted_actions=_ALL_ACTIONS,
            obligations=(),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='MIT',
            name='MIT License',
            granted_actions=_ALL_ACTIONS,
            obligations=('Retain the copyright notice and license text',),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='ISC',
            name='ISC License',
            granted_actions=_ALL_ACTIONS,
            obligations=('Retain the copyright notice and license text',),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='BSD-2-Clause',
            name='BSD 2-Clause Simplified License',
            granted_actions=_ALL_ACTIONS,
            obligations=('Retain the copyright notice and license text',),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='BSD-3-Clause',
            name='BSD 3-Clause New or Revised License',
            granted_actions=_ALL_ACTIONS,
            obligations=(
                'Retain the copyright notice and license text',
                'Do not use contributor names to endorse derived products',
            ),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='Apache-2.0',
            name='Apache License 2.0',
            granted_actions=_ALL_ACTIONS,
            obligations=(
                'Retain the copyright notice and license text',
                'Include the NOTICE file when the original ships one',
                'State significant modifications',
            ),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='MPL-2.0',
            name='Mozilla Public License 2.0',
            granted_actions=_ALL_ACTIONS,
            obligations=('Disclose the source of modified MPL-covered files',),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='CC-BY-4.0',
            name='Creative Commons Attribution 4.0',
            granted_actions=_ALL_ACTIONS,
            obligations=_ATTRIBUTION,
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='CC-BY-SA-4.0',
            name='Creative Commons Attribution-ShareAlike 4.0',
            granted_actions=_ALL_ACTIONS,
            obligations=(*_ATTRIBUTION, 'License derivatives under the same terms'),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='CC-BY-ND-4.0',
            name='Creative Commons Attribution-NoDerivatives 4.0',
            granted_actions=(RightsAction.RESELL, RightsAction.REDISTRIBUTE),
            obligations=(*_ATTRIBUTION, 'Do not distribute modified versions'),
            commercial_use_allowed=True,
            modification_allowed=False,
            storefront_listing=StorefrontListing.PAID_OK,
        ),
        LicenseGrant(
            license_id='CC-BY-NC-4.0',
            name='Creative Commons Attribution-NonCommercial 4.0',
            granted_actions=(RightsAction.REDISTRIBUTE, RightsAction.MODIFY),
            obligations=(*_ATTRIBUTION, 'Non-commercial use only'),
            commercial_use_allowed=False,
            modification_allowed=True,
            storefront_listing=StorefrontListing.NOT_LISTED,
        ),
        LicenseGrant(
            license_id='CC-BY-NC-SA-4.0',
            name='Creative Commons Attribution-NonCommercial-ShareAlike 4.0',
            granted_actions=(RightsAction.REDISTRIBUTE, RightsAction.MODIFY),
            obligations=(
                *_ATTRIBUTION,
                'Non-commercial use only',
                'License derivatives under the same terms',
            ),
            commercial_use_allowed=False,
            modification_allowed=True,
            storefront_listing=StorefrontListing.NOT_LISTED,
        ),
        LicenseGrant(
            license_id='CC-BY-NC-ND-4.0',
            name='Creative Commons Attribution-NonCommercial-NoDerivatives 4.0',
            granted_actions=(RightsAction.REDISTRIBUTE,),
            obligations=(
                *_ATTRIBUTION,
                'Non-commercial use only',
                'Do not distribute modified versions',
            ),
            commercial_use_allowed=False,
            modification_allowed=False,
            storefront_listing=StorefrontListing.NOT_LISTED,
        ),
        LicenseGrant(
            license_id='GPL-2.0-only',
            name='GNU General Public License v2.0 only',
            granted_actions=(
                RightsAction.RESELL,
                RightsAction.REDISTRIBUTE,
                RightsAction.MODIFY,
            ),
            obligations=(
                'Provide the complete corresponding source',
                'License copies and derivatives under the same terms',
                'Retain copyright notices',
            ),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.FREE_ONLY,
        ),
        LicenseGrant(
            license_id='GPL-3.0-only',
            name='GNU General Public License v3.0 only',
            granted_actions=(
                RightsAction.RESELL,
                RightsAction.REDISTRIBUTE,
                RightsAction.MODIFY,
            ),
            obligations=(
                'Provide the complete corresponding source',
                'License copies and derivatives under the same terms',
                'Retain copyright notices',
                'Grant patent rights to recipients',
            ),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.FREE_ONLY,
        ),
        LicenseGrant(
            license_id='AGPL-3.0-only',
            name='GNU Affero General Public License v3.0 only',
            granted_actions=(
                RightsAction.RESELL,
                RightsAction.REDISTRIBUTE,
                RightsAction.MODIFY,
            ),
            obligations=(
                'Provide the complete corresponding source',
                'License copies and derivatives under the same terms',
                'Offer source to users interacting with it over a network',
            ),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.FREE_ONLY,
        ),
        LicenseGrant(
            license_id='LGPL-3.0-only',
            name='GNU Lesser General Public License v3.0 only',
            granted_actions=(
                RightsAction.RESELL,
                RightsAction.REDISTRIBUTE,
                RightsAction.MODIFY,
            ),
            obligations=(
                'Provide the source of the LGPL-covered work',
                'Allow recipients to relink against a modified version',
            ),
            commercial_use_allowed=True,
            modification_allowed=True,
            storefront_listing=StorefrontListing.FREE_ONLY,
        ),
    )
