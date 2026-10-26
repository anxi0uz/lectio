# Lectio: visual and interaction QA

final result: passed

## Scope and evidence

Product adaptation of the supplied Mentora dashboard, grounded in `../BACKEND_API.md`. Russian copy, Lectio identity, supported backend features, additional tabs, and a labelled demo course intentionally replace Mentora-specific ratings, reviews, certificates, locked lessons and unrelated navigation. This is an implemented Lectio frontend based on the reference composition, not an assertion of pixel-identical English content.

- Source: `docs/qa/reference.png`, downloaded from the exact supplied Dribbble shot. Original 4800 × 3600 pixels; normalized to 1710 × 1283 for comparison, including the reference's presentation canvas.
- Implementation: `docs/qa/desktop.png`, Chrome viewport 1710 × 1283 CSS pixels, screenshot 1710 × 1283 pixels, effective screenshot density 1×. State: demo course, first lesson, Overview, AI notes, paused, light theme.
- Full comparison: `docs/qa/comparison.png`, source and implementation in one image, 3420 × 1323 pixels with labels. Canvas padding differs intentionally from the static presentation frame; compare app-owned regions rather than canvas margins.
- Focused comparison: `docs/qa/comparison-detail.png`, source and implementation video, tabs and overview typography together. Crops are normalized for close inspection.
- Responsive evidence: `docs/qa/mobile.png`, full-page capture at 390 × 844 CSS viewport, effective screenshot density 1×. Width measured in browser: 390 px viewport / 390 px document, no horizontal document overflow. Horizontal tabs and bounded transcript/playlist have intentional local scrolling.
- Browser: user's Chrome, explicitly authorized by the user. The original Dribbble page was inspected there as well as the downloaded source image. Preview remains running at `http://127.0.0.1:5173/` and the output tab is marked to remain open. Temporary viewport override reset after QA.

## Comparison history and fixes

1. [P2, fixed] Initial desktop body text, transcript and tabs were too small relative to the supplied visual. Increased desktop body to 16px, notes to 15px, tabs to 15px, metadata to 13px and navigation to 15px; strengthened reading contrast. Verified in final full-view and focused comparison. Main heading remains 31px, with clear separation from supporting text.
2. [P2, fixed] Generated instructor frame was too wide and AI header too short relative to the source's player/assistant relationship. Enlarged poster crop by 12% on desktop, set AI header to 122px, increased its icon and adjusted the transcript viewport. Final comparison shows the warm instructor image at the intended scale and the notes/playlist aligned in the right column.
3. [P2, fixed] Reusing a course/dash collection across navigation could render an incompatible response shape. Clear collection state on navigation and guard dashboard data. Verified course → dashboard navigation in Chrome, including mobile menu closure.
4. [P2, fixed] Personal mutations could reload the player while watching. Separated lecture reloads from personal/list invalidation, and tracked the last position per lecture. Note operations in the global collection explicitly use remote data, independently of the last opened demo lecture.
5. [P3, fixed] Instructor avatar crop showed the lower face. Adjusted crop origin and scale; final desktop screenshot shows the face correctly.

## Required fidelity surfaces

- **Fonts and typography:** bundled Manrope variable, including Cyrillic; no CDN dependency. Geometric sans character retained; explicit body, small UI and title hierarchy. Russian labels wrap within the reference-like grid; the long real lecture title also fits without horizontal overflow. Exact source font is not claimed.
- **Spacing and layout rhythm:** light application frame, narrow left navigation, separate course header, 1.63:1 content split, large player and bordered right cards. Card padding, 5–9px radii, restrained elevation, playlist rhythm and reading gaps checked in combined images. Extra top utility bar, instructor footer and functional tabs are intentional Lectio additions. At tablet widths the assistant shifts below the lesson; at mobile it stacks with drawer navigation.
- **Colors and tokens:** white reading surfaces, cool light-gray canvas, thin gray borders, graphite active controls, muted secondary text. Readable body contrast strengthened over early capture. Warm yellow instructor image remains the dominant color area.
- **Image quality:** generated 1584 × 992 instructor poster is sharp and matches the warm studio, centered dark-haired instructor and mustard shirt art direction. It is clearly demo artwork and is not presented as a frame from the real geometry video. Real lecture videos render the actual backend file. Phosphor supplies UI icons; no hand-drawn icon assets or CSS illustration substitutes.
- **Copy/content:** Russian labels map to actual API operations. Demo badge and playback dialog clearly distinguish examples from live content. No invented ratings, confidence percentages, certificates, private courses or server chat persistence. Processing progress is labelled as the current stage; sum of playback positions is not labelled as measured learning time.

## Interaction verification

Verified in Chrome:

- Restoring the existing backend session and role without storing access tokens in localStorage.
- Loading the real library and opening the geometry lecture.
- Actual video metadata: duration 889.466 seconds, readyState 4; play changed paused to false; pause worked.
- Clicking transcript at 00:28 moved actual media currentTime to 28.36 seconds.
- Loading actual Markdown summary, chapters, transcript and terms from the API.
- Semantic search “теорема Пифагора” returned actual ranked fragments with timestamps.
- Actual Q&A returned the theorem formula and six timestamped sources. Inline source citations and source chips use the same seek operation.
- Demo note creation, editing and deletion; demo favorite add/remove, without server mutations.
- Course → dashboard navigation, teacher material list and add-material form (no new production content submitted).
- Cmd+K opened search, Escape closed it; modal focus initialized to input and remained within dialog.
- Mobile menu opens/closes, navigation works, no document overflow at 390px.
- Browser console error/warning logs inspected after interactions: none.

`npm test`: five meaningful API-client tests passed (rotating parallel refresh, multipart/204, no duplicate POST on network failure, request ID on business failure, failed session refresh). `npm run build`: passed after final source changes.

## Remaining limits and P3 polish

- Backend mutation forms are wired to documented contracts; real upload/import/delete/profile mutations were not executed during QA. Demo note persistence was exercised separately. Manual testing of large uploads and each browser's media codecs remains environment-dependent.
- Initial catalog/course lists load up to 200 lectures; broader pagination is documented in README.
- Russian font metrics, the newly generated instructor, the real API's title/content and the additional Lectio actions differ from Mentora by design. No actionable P0/P1/P2 visual findings remain for this adapted frontend.

## Implementation checklist

- [x] Reference captured and inspected.
- [x] Full-view and focused combined comparisons opened.
- [x] Earlier typography/image/card-rhythm issues fixed and recaptured.
- [x] Primary live read/play/search/AI scenarios verified.
- [x] Demo mutations and mobile layout verified.
- [x] Final source builds and API tests pass.
- [x] Local preview kept running and temporary viewport reset.
