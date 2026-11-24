// English dictionary. Must mirror vi.js key-for-key.
// Every number shown must come from the project report; see the claims table in README.md.

const en = {
  brand: {
    // Slogan NOT FINAL: edit only this key (shared by hero, footer and page titles).
    slogan: 'Trash with an address.',
  },

  common: {
    skip: 'Skip to main content',
    disabledHint: 'Not active yet: this feature is coming soon.',
    refsTitle: 'References',
    refsNote: 'Numbers in square brackets match the reference list of the project report. Sources are in Vietnamese unless noted.',
    refLabel: 'Reference',
    loading: 'Loading…',
  },

  meta: {
    home: 'CleanSight',
    tryAi: 'Try the AI — CleanSight',
    lab: 'Calibration lab — CleanSight',
    drainLab: 'Draw the drain zone — CleanSight',
    city: 'Customer map demo (simulated) — CleanSight',
    notFound: 'Page not found — CleanSight',
  },

  nav: {
    label: 'Main navigation',
    problem: 'Problem',
    solution: 'Solution',
    how: 'How it works',
    tryAi: 'Try the AI',
    lab: 'Calibration lab',
    city: 'Map demo',
    contact: 'Contact',
    cta: 'Talk about a pilot',
    menuOpen: 'Open menu',
    menuClose: 'Close menu',
    langGroup: 'Language',
    langVi: 'Tiếng Việt',
    langEn: 'English',
    homeLink: 'CleanSight, go to home page',
  },

  footer: {
    blurb:
      'CleanSight monitors street litter and drain inlets with fixed cameras and computer vision, so crews collect in the right place at the right time.',
    pagesTitle: 'Explore',
    contactTitle: 'Contact',
    sdgTitle: 'SDG 11',
    sdgText: 'Working towards targets 11.6, 11.5 and 11.7 of the UN Sustainable Development Goal 11.',
    prototypeNote: 'Research prototype. Interactive features are still being built.',
    copyright: '© 2026 CleanSight',
  },

  home: {
    hero: {
      eyebrow: 'Street-litter monitoring with computer vision',
      value:
        'A fixed camera takes regular photos, AI measures litter and drain-inlet blockage, and a map shows crews where to clean first.',
      ctaPrimary: 'See how it works',
      ctaSecondary: 'Try the AI',
      imgAlt:
        'Concrete kerb beside an asphalt lane, with a printed marker sheet, a plastic box, a plastic cup and a snack wrapper on the ground.',
      caption: 'Test photo. Not live data.',
    },
    problem: {
      eyebrow: 'The problem',
      title: 'Street waste',
      lead: 'Huge volumes, hotspots that keep coming back, and tens of thousands of drain inlets to watch.',
      stats: [
        { value: '14,000', label: 'tonnes of household solid waste generated every day in Ho Chi Minh City', refs: [1] },
        { value: '~68,000', label: 'drain inlets in Ho Chi Minh City; many are sealed by trash', refs: [13] },
        {
          value: '59/74',
          label: 'litter pollution hotspots had been cleared but came back (March 2026 report)',
          refs: [11],
        },
      ],
      points: [
        {
          title: 'Fixed collection schedules',
          text: 'Collection runs on set routes and time slots, not on how much litter is actually on the street.',
        },
        {
          title: 'Found by patrols or complaints',
          text: 'Litter that appears between rounds is only noticed when a patrol passes or a resident reports it.',
        },
        {
          title: 'Blocked drains cause flooding',
          text: 'Heavy rain washes litter into drain inlets. On 23 April 2021, trash-blocked inlets flooded about 200 m of Phạm Văn Đồng Boulevard.',
          refs: [9],
        },
      ],
    },
    solution: {
      eyebrow: 'The solution',
      title: 'CleanSight answers three questions',
      lead: 'Each camera watches one drain inlet and the road around it. The output is a clear number and a place on the map.',
      questions: [
        {
          title: 'How much litter is there?',
          text: 'An area litter level on four steps: low, medium, high, severe.',
        },
        {
          title: 'Where is it, and how large?',
          text: 'Litter zones are drawn on the map by latitude and longitude, with an estimated area in square metres.',
        },
        {
          title: 'Is the drain inlet covered?',
          text: 'Drain blockage is reduced to three states: low, watch, clear now.',
        },
      ],
      note: 'CleanSight supports scheduled collection, patrols and citizen reports. It does not replace them.',
    },
    how: {
      eyebrow: 'How it works',
      title: 'From one photo to one point on the map',
      lead: 'After a one-time installation and calibration, the system runs on its own.',
      figLabel: 'How CleanSight works',
      blocks: [
        { title: 'Camera', text: 'Captures a photo about every minute.' },
        { title: 'Server', text: 'Receives and queues photos.' },
        { title: 'AI analysis', text: 'Finds litter and drain inlets.' },
        { title: 'Alert map', text: 'Which roads and drains to clear first.' },
      ],
      rain: { title: 'Rain forecast', text: 'raises the alert one level' },
    },
    deploy: {
      eyebrow: 'Deployment',
      title: 'Up and running in 3 steps',
      lead: 'Each drain inlet needs one camera and a single calibration.',
      steps: [
        { title: 'Mount the camera', text: 'Mount a fixed camera facing the drain inlet and the road around it.' },
        { title: 'Calibrate once', text: 'All it takes is a printed sheet and a ruler. Once calibrated, the sheet is put away.' },
        { title: 'Follow the map', text: 'The map shows which roads and drains need clearing; crews go to the right place.' },
      ],
    },
    newness: {
      eyebrow: 'What is new',
      title: 'Three things done differently',
      lead: 'Measure the cause of blocked drains, in a form crews can use straight away.',
      features: [
        {
          title: 'Fixed drain zone',
          text: 'The drain zone is set once while the inlet is clean, so a fully covered inlet can still be measured, exactly when flood risk is highest.',
        },
        {
          title: 'Three easy states',
          text: 'Temporal smoothing removes flicker and leaves three clear states: low, watch, clear now.',
        },
        {
          title: 'On the map with one sheet of paper',
          text: 'One printed marker sheet and one ruler measurement are enough to place litter on the map. No extra sensors.',
        },
      ],
    },
    sdg: {
      title: 'Contributing to SDG 11: Sustainable cities and communities',
      lead: 'Expected impact once deployed, to be verified in field pilots.',
      primary: 'primary target',
      targets: [
        { code: '11.6', text: 'Urban environment: detecting and measuring street litter' },
        { code: '11.5', text: 'Fewer disaster losses: clearing drain inlets before the rain' },
        { code: '11.7', text: 'Public spaces: pavements and roads free of litter' },
      ],
    },
    contact: {
      eyebrow: 'Contact',
      title: 'Pilot CleanSight with us',
      lead: 'We would like to talk with the people who keep streets clean and drain inlets clear.',
      audiences: [
        {
          title: 'Environmental-service units',
          text: 'See litter that appears between collection rounds; send people and vehicles where they are needed first.',
        },
        {
          title: 'Wards and communes',
          text: 'Since 1 January 2026, commune-level People’s Committees run public sanitation. Track litter and drain inlets without waiting for complaints.',
          refs: [11],
        },
        {
          title: 'Market and residential-area managers',
          text: 'Spot litter and covered drain inlets within the area you manage.',
        },
      ],
      emailTitle: 'Email',
    },
  },

  lab: {
    hero: {
      eyebrow: 'Calibration lab',
      title: 'Try the two hands-on setup steps',
      lead: 'A person sets a camera up once. Try the two steps that need human hands: calibrating the camera with a printed board, and outlining the drain inlet.',
    },
    banner: {
      title: 'Both labs run live on the team’s laptop',
      text: 'They work while the live demo is online (the status below shows it). The photos are the team’s own samples, and nothing is written to disk. The lab pages are in English.',
    },
    board: {
      title: 'Calibrate with the board, draw litter on the map',
      text: 'Detect the printed ArUco board in a photo, place it on the map, preview what the camera sees, then send a photo with litter and see the litter regions with their position and area in square metres.',
      cta: 'Open the board lab',
    },
    drain: {
      title: 'Draw the drain zone, measure how covered it is',
      text: 'Outline the drain inlet on a photo, then measure how much of that zone is covered by litter. The zone is drawn by a person, so a fully covered inlet still gets a number.',
      cta: 'Open the drain lab',
    },
    note: 'Limits, stated plainly: single photos from one session, one operator, daytime; the AI model still misses some litter; positions assume flat ground and a camera that does not move after calibration.',
  },

  tryAi: {
    hero: {
      eyebrow: 'Try the AI',
      title: 'See how the AI reads litter',
      lead: 'Pick a sample photo, or upload your own while the live demo is online, to see how the AI reads litter.',
    },
    banner: {
      title: 'Samples any time, your own photo while the live demo is online',
      text: 'Sample results are computed in advance. Your own photo is analysed on request by a computer run by the CleanSight team. The live demo is online whenever that computer is switched on; the status chip shows whether it is.',
    },
    upload: {
      title: 'Choose a photo',
      samplesTitle: 'Sample photos',
      ownTitle: 'Or upload your own photo',
      drop: 'Drag and drop a photo, or click to choose',
      formats: 'JPG or PNG',
    },
    live: {
      status: {
        checking: 'Checking the live demo…',
        online: 'Live demo: online',
        offline: 'Live demo: offline',
      },
      onlineNote: 'Your browser shrinks the photo and removes its metadata (such as location) before sending it.',
      offlineNote:
        'The live demo runs on a computer operated by the team. When that computer is off, only the sample photos work.',
      preparing: 'Preparing your photo…',
      analysing: 'Analysing your photo…',
      badge: 'Your photo',
      alt: 'Your photo with the model’s outlines drawn on it.',
      note: 'This is the AI’s estimate for your photo. The demo is designed for street-level photos of the ground and drain inlets; other kinds of photo can give meaningless results.',
      retryAfter: 'Please wait about {n} seconds.',
      errors: {
        invalid_image: 'This file could not be read as a photo. Try another JPG or PNG.',
        unsupported_type: 'Only JPG and PNG photos are supported.',
        too_big: 'This file is too large. Choose a photo under 25 MB.',
        too_large: 'This photo has too many pixels. Choose a smaller one.',
        too_small: 'This photo is too small to analyse.',
        too_dark: 'This photo is too dark to analyse. The demo works on daytime photos.',
        rate_limited: 'Too many photos sent.',
        busy: 'The demo is busy right now. Please try again in a few seconds.',
        not_ready: 'The live demo is starting. Please try again in a moment.',
        network: 'Could not reach the live demo. It may be offline; try again later.',
        timeout: 'The analysis took too long. Please try again.',
        server: 'The live demo ran into a problem. Please try again.',
      },
    },
    samples: {
      litter: {
        label: 'Litter on the kerb',
        alt: 'Concrete kerb beside an asphalt lane. A printed marker sheet, two small boxes, a plastic cup and a snack wrapper lie on the ground.',
        note: 'The model outlined the snack wrapper and the cup. It also outlined the printed marker sheet and the open box in front of it as one piece of litter, which is wrong, and it missed the white box on the right.',
      },
      clean: {
        label: 'Clean pavement',
        alt: 'Paved footpath beside a clipped hedge. A few fallen leaves and flowers lie on the tiles.',
        note: 'There is almost no litter here. The model outlined one fallen flower as litter, which is a false alarm. The area is so small that the result stays below the Low level.',
      },
      drain: {
        label: 'Drain inlet',
        alt: 'Grated drain inlet at the edge of a road, next to a concrete kerb. A small object sits on the grate.',
        note: 'A drain inlet is clearly visible, but the model did not detect it, and it found no litter. Detecting drains directly is a known weakness, which is why CleanSight measures litter inside a drain zone set once for each camera.',
      },
    },
    result: {
      title: 'Analysis result',
      badge: 'Pre-computed sample',
      annotatedAlt: 'Sample photo with the model’s outlines drawn on it.',
      caption: 'Blue outlines mark what the model detected as litter. The number on each outline is the model’s score for that outline. No outlines means the model found nothing.',
      metricTrash: 'Area litter level',
      metricDrain: 'Drain blockage',
      ofFrame: 'of the frame',
      drainNone: 'Not detected',
      scaleTitle: 'Litter-level scale',
      levels: ['Low', 'Medium', 'High', 'Severe'],
      belowLow: 'Below Low (under 1%)',
      thresholds: 'Calibrated thresholds: 1% · 5% · 10% · 20% of the frame area',
      noteTitle: 'About this result',
      disclaimer: 'AI estimate. The model can miss litter and can outline things that are not litter.',
    },
    privacy: {
      title: 'Privacy',
      text: 'When you upload a photo, it is sent over an encrypted connection to a computer run by the CleanSight team, analysed in memory and not saved. Please do not upload photos showing people or vehicle plates.',
    },
  },

  city: {
    hero: {
      eyebrow: 'Customer view · simulated',
      title: 'A whole city on one screen',
      lead: 'What a customer sees once the cameras are installed and set up: where litter is, how covered each drain inlet is, and where crews should go first.',
    },
    banner: {
      title: 'Simulated data',
      text: 'The cameras on this page, their positions, readings and litter outlines are generated for illustration. They are not measurements and not a real customer. The status rules (median of the last 5 readings, with a delay before a status goes back down) are the product’s own.',
      snapshot: 'Snapshot: {time} (UTC+7)',
    },
    state: {
      clean: { name: 'Needs cleaning', letter: 'N', hint: 'Drain zone covered from 50% (stays until it falls below 35%)' },
      watch: { name: 'Watch', letter: 'W', hint: 'Covered from 20% (stays until it falls below 12%)' },
      clear: { name: 'Low', letter: 'L', hint: 'Drain zone mostly free of litter' },
      collecting: { name: 'No status yet', letter: '?', hint: 'Fewer than 3 readings (just installed)' },
      offline: { name: 'Offline', letter: '×', hint: 'No frame in the last 15 minutes' },
    },
    summary: {
      label: 'Cameras by status (select one to filter)',
      cameras: 'cameras',
      all: 'All',
      litter: 'Litter outlined in the latest frames',
    },
    map: {
      label: 'Map of the simulated cameras',
      hint: 'Zoom in on a camera to see the area it watches, its drain zone and the litter the AI outlined.',
      reset: 'Back to the whole city',
      zone: 'Zone {n}',
      zoneTip: 'Zone {n}: {c} cameras, {w} need cleaning',
      pinTip: '{id}: {state}',
      key: { title: 'Map key', view: 'Area the camera sees', drain: 'Drain zone', litter: 'Litter outlined by the AI' },
      popupRegion: 'Litter region {i}: {a} m²',
      popupDrain: 'on the drain zone',
      tipDrain: 'Drain inlet',
      tipCamera: 'Camera {id}',
    },
    list: {
      title: 'Where to go first',
      lead: 'Ordered the way the product orders them: status first, then how covered the drain zone is.',
      showing: 'Showing {n} of {total} cameras',
      empty: 'No camera has this status.',
      forDuration: 'for {d}',
      drain: 'Drain {p}',
    },
    card: {
      title: 'Camera {id}',
      zone: 'Zone {n}',
      simulated: 'Simulated',
      close: 'Close',
      show: 'Show on the map',
      statusFor: '{state} for {d}',
      drainTitle: 'Drain inlet',
      coverage: 'Covered by litter (median of the last 5 readings)',
      readings: 'Last readings',
      readingsHelp: 'The status follows the median of these readings, so one odd frame does not change it.',
      thresholds: 'Watch from 20%, Needs cleaning from 50%.',
      latestTitle: 'Latest frame',
      frameTime: 'Frame time',
      litterPct: 'Litter in view',
      litterLevel: 'Litter level',
      alertLevel: 'Alert level',
      regions: 'Litter outlined',
      regionsValue: '{n} regions, {a} m² in total',
      noRegions: 'No litter outlined',
      regionRow: 'Region {i}: {a} m²',
      onDrain: 'on the drain zone',
      collecting: 'Installed a moment ago. A status needs at least 3 readings within 15 minutes ({n} so far).',
      offline: 'No frame for {d} before the snapshot (last frame {time}).',
      noFrame: 'No frame received yet.',
      setup: 'Mounted about {h} m high and aimed at the drain inlet. Calibration and drain zone are set (simulated).',
    },
    level: { normal: 'Normal', low: 'Low', medium: 'Medium', high: 'High', critical: 'Critical' },
    duration: { lessThanMin: 'under a minute', min: '{n} min', hour: '{h} h', hourMin: '{h} h {m} min', day: '{d} d {h} h' },
    how: {
      title: 'How to read this page',
      items: [
        'Each camera watches one drain inlet and the road around it.',
        'The drain status uses the median of the last 5 readings (how much of the drain zone litter covers). It moves to Watch at 20% and to Needs cleaning at 50%, and goes back down only below 12% and 35%, so it does not flicker.',
        'A camera needs at least 3 readings within 15 minutes to show a status; until then it shows “No status yet”.',
        'The map draws what each camera outlined as litter, with its area in square metres. Positions come from a one-time calibration with a printed board.',
      ],
      limitsTitle: 'What this demo does not show',
      limits: [
        'Per-road alerts and rain: the product can also group cameras by road and raise alerts when rain is coming. This page shows cameras only.',
        'History: the product keeps recent readings only, so this page shows the current state.',
        'Real-world limits: daytime only, fixed cameras and flat ground. The AI model still misses some litter, and this simulation does not reproduce that.',
      ],
    },
    load: {
      loading: 'Loading the simulated data…',
      error: 'The simulated data could not be loaded. Please reload the page.',
    },
  },

  notFound: {
    code: '404',
    title: 'Page not found',
    text: 'The page you are looking for does not exist or has moved.',
    button: 'Back to home',
  },
};

export default en;
