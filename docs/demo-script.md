# Kịch bản demo dự kiến

Trạng thái: checklist cho M2 và M7; chưa phải kết quả demo đã chạy.

Nguồn: [use cases và Definition of Done](../plan.md), [roadmap](implementation-roadmap.md).

## Chuẩn bị

- [ ] Chạy stack/migrations/seed bằng các lệnh đã triển khai và kiểm chứng ở thời điểm demo.
- [ ] Dùng account giả Engineering employee, Engineering IT, Operations employee và admin; không ghi password/key vào video.
- [ ] Corpus đã publish, status mô phỏng có nhãn rõ, quota đủ cho demo; chọn live hay fake và ghi rõ.
- [ ] Biết cách mở trace đã lọc, ticket detail và nguồn tài liệu. Fake demo chỉ minh họa hành vi, không minh chứng model quality.
- [ ] Với demo V1, bật memory trước hội thoại đầu và xác nhận fact thiết bị được đề xuất ở bước 1; không bật muộn rồi trông đợi ứng dụng tự quét ticket cũ.

## Demo sớm M2

1. Login employee, mở chat và hỏi cách cài VPN trên Ubuntu.
2. Thấy trạng thái tra cứu; mở citation đúng tài liệu/trang/section.
3. Hỏi câu ngoài corpus: agent hỏi thêm hoặc nói thiếu căn cứ.
4. Refresh, vẫn xem được lịch sử mà không tự gửi lại câu hỏi.
5. Đối chiếu trace và baseline đo được; nêu rõ ticket/MCP/memory chưa phải điều kiện M2.

## Demo V1

| Bước | Thao tác | Bằng chứng mong đợi |
|---|---|---|
| 1 | Báo Docker certificate trên laptop Ubuntu | Hỏi phần còn thiếu, tìm đúng runbook và citation |
| 2 | Xác nhận bước đã thử nhưng vẫn lỗi, yêu cầu ticket | Preview có nội dung/severity/device/expiry; chưa có ticket mới |
| 3 | Refresh rồi approve hai lần | Preview phục hồi; đúng một ticket với ID từ DB |
| 4 | IT đúng phòng ban cập nhật ticket resolved | Trạng thái/audit đúng, không coi lúc tạo ticket là resolved |
| 5 | Mở memory settings kiểm tra fact đã xác nhận và sự cố vừa xử lý | Fact đúng thiết bị; incident record đã tồn tại phản ánh ticket resolved |
| 6 | Tạo conversation mới hỏi về máy hôm trước | Đúng thiết bị/sự cố; hỏi lại khi có nhiều khả năng |
| 7 | Xóa/tắt memory rồi mở lượt mới | Không dùng lại fact đã xóa/tắt |
| 8 | Đổi sang user khác thử link ticket/source riêng | Không lộ nội dung hoặc tiêu đề trái quyền |
| 9 | Admin đổi VPN sang down mô phỏng, hỏi qua chat | Business tool thật qua MCP; trả status + thời điểm + nhãn mô phỏng |
| 10 | Admin upload version mới, chờ ready rồi publish | Câu trả lời mới dùng version hiện hành, ACL vẫn đúng |

Test recovery/Redis/worker crash nên trình bày bằng automated test và một tình huống kiểm soát; không gây lỗi vào database đang chứa dữ liệu cần giữ chỉ để quay video.

## Bàn giao

- [ ] Video ngắn có luồng chính, link nguồn và giới hạn còn lại.
- [ ] Link [reports](../reports/PLAN.md) cho metrics; không dùng con số mục tiêu làm kết quả.
- [ ] Có kết quả clean-machine và restore drill vào target test riêng.
- [ ] Phân biệt rõ dữ liệu mô phỏng, hành vi fake provider và kết quả dùng model thật.
