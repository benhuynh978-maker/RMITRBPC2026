// Từ điển tiếng Việt. Mọi khóa phải có trong en.js (cùng cấu trúc).
// Mọi con số hiển thị phải lấy từ báo cáo dự án; xem bảng đối chiếu trong README.md.

const vi = {
  brand: {
    // Slogan CHƯA CHỐT: chỉ sửa ở khóa này (dùng chung cho hero, footer, tiêu đề trang).
    slogan: 'Rác có địa chỉ.',
  },

  common: {
    skip: 'Bỏ qua, đến nội dung chính',
    comingSoon: 'Sắp ra mắt',
    disabledHint: 'Chưa hoạt động: tính năng sắp ra mắt.',
    refsTitle: 'Tài liệu tham khảo',
    refsNote: 'Số trong ngoặc vuông khớp với danh mục tài liệu tham khảo của báo cáo dự án.',
    refLabel: 'Tài liệu tham khảo',
    loading: 'Đang tải…',
  },

  meta: {
    home: 'CleanSight',
    tryAi: 'Thử AI — CleanSight',
    notFound: 'Không tìm thấy trang — CleanSight',
  },

  nav: {
    label: 'Điều hướng chính',
    problem: 'Vấn đề',
    solution: 'Giải pháp',
    how: 'Cách hoạt động',
    tryAi: 'Thử AI',
    contact: 'Liên hệ',
    cta: 'Liên hệ thí điểm',
    menuOpen: 'Mở menu',
    menuClose: 'Đóng menu',
    langGroup: 'Ngôn ngữ',
    langVi: 'Tiếng Việt',
    langEn: 'English',
    homeLink: 'CleanSight, về trang chủ',
  },

  footer: {
    blurb:
      'CleanSight giám sát rác đường phố và miệng cống bằng camera cố định và thị giác máy tính, giúp thu gom đúng chỗ, đúng lúc.',
    pagesTitle: 'Nội dung',
    contactTitle: 'Liên hệ',
    sdgTitle: 'SDG 11',
    sdgText: 'Hướng tới các chỉ tiêu 11.6, 11.5 và 11.7 của Mục tiêu Phát triển Bền vững số 11 của Liên Hợp Quốc.',
    prototypeNote: 'Nguyên mẫu nghiên cứu. Các tính năng tương tác đang được hoàn thiện.',
    copyright: '© 2026 CleanSight',
  },

  home: {
    hero: {
      eyebrow: 'Giám sát rác đường phố bằng thị giác máy tính',
      value:
        'Camera cố định chụp định kỳ, AI đo lượng rác và mức che miệng cống, bản đồ cho biết nơi cần dọn trước.',
      ctaPrimary: 'Xem cách hoạt động',
      ctaSecondary: 'Thử AI',
      imgAlt:
        'Mép đường bê tông cạnh làn đường nhựa, một tờ giấy in mẫu đánh dấu, hộp nhựa, cốc nhựa và bao bì rơi trên mặt đất.',
      caption: 'Ảnh thử nghiệm. Chưa phải dữ liệu thật.',
    },
    problem: {
      eyebrow: 'Vấn đề',
      title: 'Rác thải đường phố',
      lead: 'Lượng rác lớn, điểm rác tái phát sinh, và hàng chục nghìn cửa thu nước cần theo dõi.',
      stats: [
        { value: '14.000', label: 'tấn chất thải rắn sinh hoạt phát sinh mỗi ngày tại TP.HCM', refs: [1] },
        { value: '~68.000', label: 'cửa thu nước tại TP.HCM; nhiều cửa bị rác bịt kín', refs: [13] },
        {
          value: '59/74',
          label: 'điểm ô nhiễm rác là điểm đã thu gom nhưng tái phát sinh (báo cáo tháng 3/2026)',
          refs: [11],
        },
      ],
      points: [
        {
          title: 'Thu gom theo lịch cố định',
          text: 'Xe gom chạy theo tuyến và khung giờ định sẵn, không theo lượng rác thực tế trên đường.',
        },
        {
          title: 'Phát hiện nhờ tuần tra, phản ánh',
          text: 'Rác xuất hiện giữa hai lượt chỉ được biết khi có người tuần tra đi qua hoặc người dân báo tin.',
        },
        {
          title: 'Rác bịt cống gây ngập',
          text: 'Mưa lớn cuốn rác vào cửa thu nước. Ngày 23/4/2021, rác bịt miệng cống làm ngập khoảng 200 m đại lộ Phạm Văn Đồng.',
          refs: [9],
        },
      ],
    },
    solution: {
      eyebrow: 'Giải pháp',
      title: 'CleanSight trả lời ba câu hỏi',
      lead: 'Mỗi camera theo dõi một miệng cống và mặt đường quanh nó. Kết quả là con số dễ hiểu và vị trí trên bản đồ.',
      questions: [
        {
          title: 'Có bao nhiêu rác?',
          text: 'Mức rác khu vực theo bốn mức: thấp, trung bình, cao, nghiêm trọng.',
        },
        {
          title: 'Rác ở đâu, rộng bao nhiêu?',
          text: 'Vùng rác được vẽ lên bản đồ theo kinh độ, vĩ độ, kèm diện tích ước tính bằng mét vuông.',
        },
        {
          title: 'Miệng cống có bị che?',
          text: 'Mức che miệng cống quy về ba trạng thái: thấp, cần theo dõi, cần dọn.',
        },
      ],
      note: 'CleanSight bổ trợ cho thu gom theo lịch, tuần tra và phản ánh của người dân, không thay thế các kênh này.',
    },
    how: {
      eyebrow: 'Cách hoạt động',
      title: 'Từ một bức ảnh đến một điểm trên bản đồ',
      lead: 'Sau khi lắp đặt và hiệu chỉnh một lần, hệ thống tự chạy.',
      figLabel: 'Sơ đồ hoạt động của CleanSight',
      blocks: [
        { title: 'Camera', text: 'Chụp ảnh khoảng mỗi phút.' },
        { title: 'Máy chủ', text: 'Nhận ảnh, xếp hàng phân tích.' },
        { title: 'AI phân tích', text: 'Tìm rác và miệng cống.' },
        { title: 'Bản đồ cảnh báo', text: 'Tuyến nào, cống nào cần dọn trước.' },
      ],
      rain: { title: 'Dự báo mưa', text: 'nâng mức cảnh báo một bậc' },
    },
    deploy: {
      eyebrow: 'Triển khai',
      title: 'Triển khai trong 3 bước',
      lead: 'Mỗi miệng cống cần một camera và một lần hiệu chỉnh.',
      steps: [
        { title: 'Lắp camera', text: 'Lắp một camera cố định hướng về miệng cống và mặt đường quanh nó.' },
        { title: 'Hiệu chỉnh một lần', text: 'Chỉ cần một tờ giấy in sẵn và một cây thước. Hiệu chỉnh xong thì cất tờ giấy đi.' },
        { title: 'Theo dõi trên bản đồ', text: 'Bản đồ cho biết tuyến nào, cống nào cần dọn; đội thu gom đến đúng chỗ.' },
      ],
    },
    newness: {
      eyebrow: 'Điểm mới',
      title: 'Ba điểm khác biệt',
      lead: 'Đo đúng nguyên nhân gây tắc cống, ở dạng đội thu gom dùng được ngay.',
      features: [
        {
          title: 'Vùng miệng cống cố định',
          text: 'Vùng cống được xác định một lần lúc cống sạch, nên rác che kín vẫn đo được, đúng lúc nguy cơ ngập cao nhất.',
        },
        {
          title: 'Ba trạng thái dễ hiểu',
          text: 'Làm mượt theo thời gian loại bỏ dao động, cho ra ba trạng thái rõ ràng: thấp, cần theo dõi, cần dọn.',
        },
        {
          title: 'Lên bản đồ bằng một tờ giấy',
          text: 'Một tờ giấy in mẫu đánh dấu và một số đo bằng thước là đủ để đưa vùng rác lên bản đồ. Không cần thêm cảm biến.',
        },
      ],
    },
    sdg: {
      title: 'Đóng góp cho SDG 11: Thành phố và cộng đồng bền vững',
      lead: 'Tác động dự kiến khi triển khai, sẽ được kiểm chứng qua thử nghiệm thực địa.',
      primary: 'chỉ tiêu chính',
      targets: [
        { code: '11.6', text: 'Môi trường đô thị: phát hiện, định lượng rác đường phố' },
        { code: '11.5', text: 'Giảm thiệt hại thiên tai: khơi thông cống trước mưa' },
        { code: '11.7', text: 'Không gian công cộng: vỉa hè, lòng đường sạch rác' },
      ],
    },
    contact: {
      eyebrow: 'Liên hệ',
      title: 'Cùng thí điểm CleanSight',
      lead: 'Chúng tôi muốn trao đổi với những đơn vị đang giữ cho đường phố sạch và miệng cống thông thoáng.',
      audiences: [
        {
          title: 'Đơn vị môi trường',
          text: 'Biết điểm rác phát sinh giữa các lượt thu gom; điều người và xe đến nơi cần trước.',
        },
        {
          title: 'Phường/xã',
          text: 'Từ 1/1/2026, UBND cấp xã trực tiếp phụ trách vệ sinh công cộng. Theo dõi điểm rác, miệng cống mà không chờ phản ánh.',
          refs: [11],
        },
        {
          title: 'Ban quản lý chợ/khu đô thị',
          text: 'Phát hiện rác và miệng cống bị che trong phạm vi quản lý.',
        },
      ],
      emailTitle: 'Email',
    },
  },

  tryAi: {
    hero: {
      eyebrow: 'Thử AI',
      title: 'Tải ảnh lên, xem AI đọc rác',
      lead: 'Trang thử AI trực tuyến đang được hoàn thiện. Giao diện dưới đây là bản xem trước.',
    },
    banner: {
      title: 'Sắp ra mắt',
      text: 'Khi mở, bạn có thể tải ảnh một miệng cống và mặt đường quanh nó để xem vùng rác, miệng cống và hai chỉ số do AI tính.',
    },
    upload: {
      title: 'Chọn ảnh',
      drop: 'Kéo thả ảnh hoặc bấm để chọn',
      formats: 'JPG hoặc PNG',
      samplesTitle: 'Hoặc chọn ảnh mẫu',
      sampleLabel: 'Ảnh mẫu',
      sampleAlt: 'Ảnh mẫu: mép đường có rác và bảng đánh dấu',
      analyze: 'Phân tích ảnh',
    },
    result: {
      title: 'Kết quả phân tích',
      imagePlaceholder: 'Ảnh đã khoanh vùng sẽ hiển thị ở đây',
      legendTrash: 'Rác',
      legendDrain: 'Miệng cống',
      metricTrash: 'Mức rác khu vực',
      metricDrain: 'Mức che miệng cống',
      empty: '—',
      scaleTitle: 'Thang mức rác',
      levels: ['Thấp', 'Trung bình', 'Cao', 'Nghiêm trọng'],
      thresholds: 'Ngưỡng hiệu chỉnh: 1% · 5% · 10% · 20% diện tích khung hình',
      drainTitle: 'Trạng thái miệng cống',
      drainStates: ['Thấp', 'Cần theo dõi', 'Cần dọn'],
      confidence: 'Mức tin cậy',
      confidenceNote: 'Chỉ để tham khảo',
    },
    privacy: {
      title: 'Quyền riêng tư',
      text: 'Khi hoạt động, ảnh chỉ được xử lý để phân tích rác và miệng cống.',
    },
  },

  notFound: {
    code: '404',
    title: 'Không tìm thấy trang',
    text: 'Trang bạn tìm không tồn tại hoặc đã được di chuyển.',
    button: 'Về trang chủ',
  },
};

export default vi;
