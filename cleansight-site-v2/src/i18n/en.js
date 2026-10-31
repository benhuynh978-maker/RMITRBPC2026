// English dictionary. Must mirror vi.js key-for-key.
// Every number shown must come from the project report; see the claims table in README.md.

const en = {
  brand: {
    // Slogan NOT FINAL: edit only this key (shared by hero, footer and page titles).
    slogan: 'Trash with an address.',
  },

  common: {
    skip: 'Skip to main content',
    comingSoon: 'Coming soon',
    disabledHint: 'Not active yet: this feature is coming soon.',
    refsTitle: 'References',
    refsNote: 'Numbers in square brackets match the reference list of the project report. Sources are in Vietnamese unless noted.',
    refLabel: 'Reference',
    loading: 'Loading…',
  },

  meta: {
    home: 'CleanSight',
    tryAi: 'Try the AI — CleanSight',
    notFound: 'Page not found — CleanSight',
  },

  nav: {
    label: 'Main navigation',
    problem: 'Problem',
    solution: 'Solution',
    how: 'How it works',
    tryAi: 'Try the AI',
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

  tryAi: {
    hero: {
      eyebrow: 'Try the AI',
      title: 'Upload a photo, see how the AI reads litter',
      lead: 'The online AI demo is still being built. The interface below is a preview.',
    },
    banner: {
      title: 'Coming soon',
      text: 'Once live, you will be able to upload a photo of a drain inlet and the road around it, and see litter zones, the inlet and two AI-computed indices.',
    },
    upload: {
      title: 'Choose a photo',
      drop: 'Drag and drop a photo, or click to choose',
      formats: 'JPG or PNG',
      samplesTitle: 'Or pick a sample photo',
      sampleLabel: 'Sample photo',
      sampleAlt: 'Sample photo: kerb with litter and a marker sheet',
      analyze: 'Analyse photo',
    },
    result: {
      title: 'Analysis result',
      imagePlaceholder: 'The annotated photo will appear here',
      legendTrash: 'Trash',
      legendDrain: 'Drain inlet',
      metricTrash: 'Area litter level',
      metricDrain: 'Drain blockage',
      empty: '—',
      scaleTitle: 'Litter-level scale',
      levels: ['Low', 'Medium', 'High', 'Severe'],
      thresholds: 'Calibrated thresholds: 1% · 5% · 10% · 20% of the frame area',
      drainTitle: 'Drain-inlet state',
      drainStates: ['Low', 'Watch', 'Clear now'],
      confidence: 'Confidence',
      confidenceNote: 'For reference only',
    },
    privacy: {
      title: 'Privacy',
      text: 'When live, photos are processed only to analyse litter and drain inlets.',
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
