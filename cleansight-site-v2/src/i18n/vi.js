// Từ điển tiếng Việt. Mọi khóa phải có trong en.js (cùng cấu trúc).
// Mọi con số hiển thị phải lấy từ báo cáo dự án; xem bảng đối chiếu trong README.md.

const vi = {
  brand: {
    // Slogan CHƯA CHỐT: chỉ sửa ở khóa này (dùng chung cho hero, footer, tiêu đề trang).
    slogan: 'Rác có địa chỉ.',
  },

  common: {
    skip: 'Bỏ qua, đến nội dung chính',
    disabledHint: 'Chưa hoạt động: tính năng sắp ra mắt.',
    refsTitle: 'Tài liệu tham khảo',
    refsNote: 'Số trong ngoặc vuông khớp với danh mục tài liệu tham khảo của báo cáo dự án.',
    refLabel: 'Tài liệu tham khảo',
    loading: 'Đang tải…',
  },

  meta: {
    home: 'CleanSight',
    tryAi: 'Thử AI — CleanSight',
    lab: 'Phòng thử hiệu chỉnh — CleanSight',
    drainLab: 'Vẽ vùng miệng cống — CleanSight',
    notFound: 'Không tìm thấy trang — CleanSight',
  },

  nav: {
    label: 'Điều hướng chính',
    problem: 'Vấn đề',
    solution: 'Giải pháp',
    how: 'Cách hoạt động',
    tryAi: 'Thử AI',
    lab: 'Phòng thử hiệu chỉnh',
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

  lab: {
    hero: {
      eyebrow: 'Phòng thử hiệu chỉnh',
      title: 'Thử hai bước cài đặt cần đến bàn tay con người',
      lead: 'Một camera chỉ cần người cài đặt một lần. Hãy thử hai bước đó: hiệu chỉnh camera bằng bảng in, và khoanh vùng miệng cống.',
    },
    banner: {
      title: 'Cả hai phòng thử chạy trực tiếp trên laptop của nhóm',
      text: 'Chúng hoạt động khi demo trực tuyến đang mở (trạng thái hiển thị bên dưới). Ảnh là ảnh mẫu của nhóm, và không có gì được ghi ra đĩa. Các trang phòng thử bằng tiếng Anh.',
    },
    board: {
      title: 'Hiệu chỉnh bằng bảng, vẽ rác lên bản đồ',
      text: 'Dò tờ bảng ArUco đã in trong ảnh, đặt nó lên bản đồ, xem trước vùng camera nhìn thấy, rồi gửi ảnh có rác để xem các vùng rác kèm vị trí và diện tích theo mét vuông.',
      cta: 'Mở phòng thử bảng',
    },
    drain: {
      title: 'Vẽ vùng cống, đo mức bị che',
      text: 'Khoanh miệng cống trên ảnh, rồi đo xem bao nhiêu phần của vùng đó bị rác che. Vùng do người vẽ nên cống bị che kín vẫn ra một con số.',
      cta: 'Mở phòng thử cống',
    },
    note: 'Giới hạn, nói thẳng: ảnh đơn trong một phiên, một người thao tác, ban ngày; mô hình AI còn bỏ sót rác; vị trí giả định mặt đất phẳng và camera không nhúc nhích sau khi hiệu chỉnh.',
  },

  tryAi: {
    hero: {
      eyebrow: 'Thử AI',
      title: 'Xem AI đọc rác',
      lead: 'Chọn một ảnh mẫu, hoặc tải ảnh của bạn lên khi demo trực tuyến đang mở, để xem AI đọc rác.',
    },
    banner: {
      title: 'Ảnh mẫu mọi lúc, ảnh của bạn khi demo trực tuyến đang mở',
      text: 'Kết quả ảnh mẫu được tính sẵn. Ảnh của bạn được phân tích theo yêu cầu bởi một máy tính do nhóm CleanSight vận hành. Demo trực tuyến mở khi máy tính đó đang bật; chấm trạng thái cho biết nó có đang mở hay không.',
    },
    upload: {
      title: 'Chọn ảnh',
      samplesTitle: 'Ảnh mẫu',
      ownTitle: 'Hoặc tải ảnh của bạn lên',
      drop: 'Kéo thả ảnh hoặc bấm để chọn',
      formats: 'JPG hoặc PNG',
    },
    live: {
      status: {
        checking: 'Đang kiểm tra demo trực tuyến…',
        online: 'Demo trực tuyến: đang mở',
        offline: 'Demo trực tuyến: đang tắt',
      },
      onlineNote: 'Trình duyệt của bạn thu nhỏ ảnh và bỏ thông tin đi kèm (như vị trí chụp) trước khi gửi.',
      offlineNote:
        'Demo trực tuyến chạy trên một máy tính do nhóm vận hành. Khi máy đó tắt, chỉ dùng được các ảnh mẫu.',
      preparing: 'Đang chuẩn bị ảnh của bạn…',
      analysing: 'Đang phân tích ảnh của bạn…',
      badge: 'Ảnh của bạn',
      alt: 'Ảnh của bạn có viền do mô hình vẽ.',
      note: 'Đây là ước tính của AI cho ảnh của bạn. Bản demo được thiết kế cho ảnh chụp mặt đất và miệng cống ở ngoài phố; ảnh loại khác có thể cho kết quả vô nghĩa.',
      retryAfter: 'Vui lòng chờ khoảng {n} giây.',
      errors: {
        invalid_image: 'Không đọc được tệp này như một bức ảnh. Hãy thử ảnh JPG hoặc PNG khác.',
        unsupported_type: 'Chỉ hỗ trợ ảnh JPG và PNG.',
        too_big: 'Tệp quá lớn. Hãy chọn ảnh dưới 25 MB.',
        too_large: 'Ảnh có quá nhiều điểm ảnh. Hãy chọn ảnh nhỏ hơn.',
        too_small: 'Ảnh quá nhỏ để phân tích.',
        too_dark: 'Ảnh quá tối để phân tích. Bản demo dùng cho ảnh chụp ban ngày.',
        rate_limited: 'Bạn đã gửi quá nhiều ảnh.',
        busy: 'Demo đang bận. Vui lòng thử lại sau vài giây.',
        not_ready: 'Demo đang khởi động. Vui lòng thử lại sau giây lát.',
        network: 'Không kết nối được tới demo trực tuyến. Có thể nó đang tắt; hãy thử lại sau.',
        timeout: 'Việc phân tích mất quá lâu. Vui lòng thử lại.',
        server: 'Demo trực tuyến gặp sự cố. Vui lòng thử lại.',
      },
    },
    samples: {
      litter: {
        label: 'Rác ở mép đường',
        alt: 'Mép vỉa bê tông cạnh làn đường nhựa. Trên mặt đất có tờ bảng đánh dấu in, hai chiếc hộp nhỏ, một cốc nhựa và một gói bánh.',
        note: 'Mô hình khoanh đúng gói bánh và cốc nhựa. Nó cũng khoanh tờ bảng đánh dấu cùng chiếc hộp mở phía trước thành một vật rác, điều này là sai, và bỏ sót chiếc hộp trắng bên phải.',
      },
      clean: {
        label: 'Vỉa hè sạch',
        alt: 'Vỉa hè lát gạch cạnh hàng cây cắt tỉa. Trên gạch có vài chiếc lá và bông hoa rụng.',
        note: 'Ở đây gần như không có rác. Mô hình khoanh nhầm một bông hoa rụng thành rác, đó là báo nhầm. Diện tích rất nhỏ nên kết quả vẫn dưới mức Thấp.',
      },
      drain: {
        label: 'Miệng cống',
        alt: 'Miệng cống có song chắn ở mép đường, cạnh bó vỉa bê tông. Có một vật nhỏ nằm trên song chắn.',
        note: 'Miệng cống nhìn thấy rõ nhưng mô hình không phát hiện được, và cũng không tìm thấy rác. Phát hiện trực tiếp miệng cống là điểm yếu đã biết, vì vậy CleanSight đo rác trong vùng cống được đặt một lần cho mỗi camera.',
      },
    },
    result: {
      title: 'Kết quả phân tích',
      badge: 'Mẫu tính sẵn',
      annotatedAlt: 'Ảnh mẫu có viền do mô hình vẽ.',
      caption: 'Viền xanh đánh dấu vùng mô hình phát hiện là rác. Số trên mỗi viền là điểm của mô hình cho viền đó. Không có viền nghĩa là mô hình không tìm thấy gì.',
      metricTrash: 'Mức rác khu vực',
      metricDrain: 'Mức che miệng cống',
      ofFrame: 'diện tích khung hình',
      drainNone: 'Không phát hiện',
      scaleTitle: 'Thang mức rác',
      levels: ['Thấp', 'Trung bình', 'Cao', 'Nghiêm trọng'],
      belowLow: 'Dưới mức Thấp (dưới 1%)',
      thresholds: 'Ngưỡng hiệu chỉnh: 1% · 5% · 10% · 20% diện tích khung hình',
      noteTitle: 'Về kết quả này',
      disclaimer: 'Ước tính của AI. Mô hình có thể bỏ sót rác và có thể khoanh cả vật không phải rác.',
    },
    privacy: {
      title: 'Quyền riêng tư',
      text: 'Khi bạn tải ảnh lên, ảnh được gửi qua kết nối mã hoá tới một máy tính do nhóm CleanSight vận hành, được phân tích trong bộ nhớ và không được lưu lại. Vui lòng không tải ảnh có người hoặc biển số xe.',
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
