"""
출석 관리 시스템 - Python GUI 버전 (PyQt5)
exe 파일로 배포 가능한 데스크톱 애플리케이션
"""

import sys
import json
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCalendarWidget, QComboBox, QGridLayout,
    QGroupBox, QDialog, QRadioButton, QButtonGroup, QMessageBox,
    QDateEdit
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor, QPalette


# ============================================
# 출석 상태 정의
# ============================================
class AttendanceStatus:
    PRESENT = "출석"
    ABSENT = "결석"
    LATE = "지각"
    EARLY = "조퇴"
    OUTING = "외출"
    SICK = "병결"

    ALL = [PRESENT, ABSENT, LATE, EARLY, OUTING, SICK]

    COLORS = {
        PRESENT: "#10b981",
        ABSENT: "#ef4444",
        LATE: "#f97316",
        EARLY: "#eab308",
        OUTING: "#a78bfa",
        SICK: "#6b7280"
    }


# ============================================
# 출석률 계산 로직
# ============================================
class AttendanceCalculator:
    """출석률 계산을 담당하는 클래스"""

    @staticmethod
    def calculate(data, total_weekdays):
        """
        출석률 계산

        Args:
            data: {날짜_문자열: 상태} 딕셔너리
            total_weekdays: 총 평일 수

        Returns:
            {
                'rate': 출석률,
                'counts': 각 상태별 횟수,
                'final_absences': 최종 결석 수
            }
        """
        if total_weekdays == 0:
            return {'rate': 100.0, 'counts': {}, 'final_absences': 0}

        # 상태별 카운트
        counts = {status: 0 for status in AttendanceStatus.ALL}
        for status in data.values():
            if status in counts:
                counts[status] += 1

        # 직접 결석
        direct_absent = counts[AttendanceStatus.ABSENT]

        # 동일 사유 중복 (각각 2회 = 결석 1회)
        late_pairs = counts[AttendanceStatus.LATE] // 2
        early_pairs = counts[AttendanceStatus.EARLY] // 2
        outing_pairs = counts[AttendanceStatus.OUTING] // 2
        same_type_penalty = late_pairs + early_pairs + outing_pairs

        # 상이 사유 중복 (나머지 합 3회 = 결석 1회)
        late_rem = counts[AttendanceStatus.LATE] % 2
        early_rem = counts[AttendanceStatus.EARLY] % 2
        outing_rem = counts[AttendanceStatus.OUTING] % 2
        mixed_type_penalty = (late_rem + early_rem + outing_rem) // 3

        # 최종 결석 수
        final_absences = direct_absent + same_type_penalty + mixed_type_penalty

        # 출석률 계산 (병결은 출석으로 인정)
        rate = ((total_weekdays - final_absences) / total_weekdays) * 100
        rate = max(0, round(rate, 1))

        return {
            'rate': rate,
            'counts': counts,
            'final_absences': final_absences
        }

    @staticmethod
    def count_weekdays(start_date, end_date):
        """주어진 기간의 평일(월~금) 수 계산"""
        count = 0
        current = start_date
        while current <= end_date:
            # 0=월요일, 6=일요일
            if current.dayOfWeek() in [1, 2, 3, 4, 5]:  # 월~금
                count += 1
            current = current.addDays(1)
        return count

    @staticmethod
    def calculate_monthly_summary(all_data, start_date):
        """
        월별 출석률 요약 계산 (현재 월 포함)

        Args:
            all_data: 전체 출석 데이터 {날짜_문자열: 상태}
            start_date: 출석 시작일 (QDate)

        Returns:
            [{
                'month': 'YYYY년 M월',
                'year_month': (year, month),  # 정렬용
                'rate': 출석률,
                'counts': 상태별 카운트,
                'weekdays': 평일 수,
                'is_current': 현재 월 여부
            }, ...]
        """
        today = QDate.currentDate()

        # 시작 월과 현재 월 계산
        start_year = start_date.year()
        start_month = start_date.month()
        current_year = today.year()
        current_month = today.month()

        results = []

        # 시작 월부터 현재 월까지 순회
        year = start_year
        month = start_month

        while True:
            # 현재 월을 초과하면 중단
            if year > current_year or (year == current_year and month > current_month):
                break

            # 현재 월인지 확인
            is_current = (year == current_year and month == current_month)

            # 해당 월의 데이터 필터링
            month_data = {}
            month_start = QDate(year, month, 1)
            month_end = QDate(year, month, month_start.daysInMonth())

            # 해당 월의 평일 수 계산
            total_weekdays = AttendanceCalculator.count_weekdays(month_start, month_end)

            # 해당 월의 출석 데이터 필터링
            current_date = month_start
            while current_date <= month_end:
                date_str = current_date.toString("yyyy-MM-dd")
                if date_str in all_data and current_date.dayOfWeek() in [1, 2, 3, 4, 5]:
                    month_data[date_str] = all_data[date_str]
                current_date = current_date.addDays(1)

            # 출석률 계산 (데이터가 없으면 100%)
            if len(month_data) == 0:
                result = {
                    'rate': 100.0,
                    'counts': {status: 0 for status in AttendanceStatus.ALL},
                    'final_absences': 0
                }
            else:
                result = AttendanceCalculator.calculate(month_data, total_weekdays)

            results.append({
                'month': f'{year}년 {month}월',
                'year_month': (year, month),
                'rate': result['rate'],
                'counts': result['counts'],
                'weekdays': total_weekdays,
                'is_current': is_current
            })

            # 다음 월로 이동
            month += 1
            if month > 12:
                month = 1
                year += 1

        return results


# ============================================
# 상태 선택 다이얼로그
# ============================================
class StatusDialog(QDialog):
    """출결 상태를 선택하는 다이얼로그"""

    def __init__(self, current_status, date_str, parent=None):
        super().__init__(parent)
        self.selected_status = current_status
        self.setWindowTitle("출결 상태 변경")
        self.setModal(True)
        self.init_ui(current_status, date_str)

    def init_ui(self, current_status, date_str):
        layout = QVBoxLayout()

        # 날짜 표시
        date_label = QLabel(f"📅 {date_str}")
        date_label.setFont(QFont("", 12, QFont.Bold))
        date_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(date_label)

        layout.addSpacing(10)

        # 라디오 버튼 그룹
        self.button_group = QButtonGroup()

        for i, status in enumerate(AttendanceStatus.ALL):
            radio = QRadioButton(status)
            radio.setFont(QFont("", 11))
            if status == current_status:
                radio.setChecked(True)

            # 색상 표시
            color = AttendanceStatus.COLORS[status]
            radio.setStyleSheet(f"""
                QRadioButton {{
                    padding: 8px;
                    margin: 2px;
                }}
                QRadioButton::indicator {{
                    width: 16px;
                    height: 16px;
                }}
                QRadioButton:checked {{
                    background-color: {color}22;
                    border-left: 3px solid {color};
                    border-radius: 4px;
                }}
            """)

            self.button_group.addButton(radio, i)
            radio.toggled.connect(lambda checked, s=status: self.on_status_changed(s, checked))
            layout.addWidget(radio)

        layout.addSpacing(10)

        # 확인 버튼
        ok_button = QPushButton("확인")
        ok_button.setFont(QFont("", 11))
        ok_button.clicked.connect(self.accept)
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        layout.addWidget(ok_button)

        self.setLayout(layout)

    def on_status_changed(self, status, checked):
        if checked:
            self.selected_status = status

    def get_status(self):
        return self.selected_status


# ============================================
# 메인 윈도우
# ============================================
class AttendanceMainWindow(QMainWindow):
    """출석 관리 시스템 메인 윈도우"""

    def __init__(self):
        super().__init__()

        # 데이터: {날짜_문자열: 상태}
        self.attendance_data = {}
        self.start_date = QDate.currentDate()
        self.end_date = self.start_date.addMonths(1)
        self.target_rate = 90

        self.init_ui()
        self.initialize_data()
        self.update_display()

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("출석 관리 시스템")
        self.setGeometry(100, 100, 1000, 700)

        # 메인 위젯
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # 메인 레이아웃
        main_layout = QVBoxLayout()

        # === 헤더 ===
        header = self.create_header()
        main_layout.addWidget(header)

        # === 통계 카드 ===
        stats = self.create_stats_cards()
        main_layout.addWidget(stats)

        # === 월별 요약 ===
        monthly_summary = self.create_monthly_summary()
        main_layout.addWidget(monthly_summary)

        # === 캘린더 ===
        calendar = self.create_calendar()
        main_layout.addWidget(calendar)

        main_widget.setLayout(main_layout)

        # 스타일 적용
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8fafc;
            }
            QGroupBox {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
                margin: 5px;
                font-weight: bold;
            }
            QLabel {
                color: #1e293b;
            }
        """)

    def create_header(self):
        """헤더 생성"""
        group = QGroupBox("📊 출석 관리 대시보드")
        layout = QVBoxLayout()

        # 첫 번째 줄: 시작일 선택
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("📅 출석 시작일:"))

        # 시작일 선택기
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setFont(QFont("", 11))
        self.start_date_edit.dateChanged.connect(self.on_start_date_changed)
        self.start_date_edit.setStyleSheet("""
            QDateEdit {
                padding: 5px;
                border: 2px solid #10b981;
                border-radius: 5px;
            }
        """)
        first_row.addWidget(self.start_date_edit)

        # 기간 표시
        self.period_label = QLabel()
        self.period_label.setFont(QFont("", 11))
        first_row.addWidget(self.period_label)

        first_row.addStretch()
        layout.addLayout(first_row)

        # 두 번째 줄: 출석률 및 목표
        second_row = QHBoxLayout()

        # 현재 출석률
        second_row.addWidget(QLabel("현재 출석률:"))
        self.rate_label = QLabel("100.0%")
        self.rate_label.setFont(QFont("", 24, QFont.Bold))
        self.rate_label.setStyleSheet("color: #10b981;")
        second_row.addWidget(self.rate_label)

        second_row.addStretch()

        # 목표 출석률 선택
        second_row.addWidget(QLabel("목표:"))
        self.target_combo = QComboBox()
        self.target_combo.addItems(["100%", "95%", "90%", "85%", "80%", "75%"])
        self.target_combo.setCurrentText("90%")
        self.target_combo.currentTextChanged.connect(self.on_target_changed)
        self.target_combo.setFont(QFont("", 11))
        second_row.addWidget(self.target_combo)

        layout.addLayout(second_row)

        group.setLayout(layout)
        return group

    def create_stats_cards(self):
        """통계 카드 생성"""
        group = QGroupBox("📈 출결 현황")
        layout = QGridLayout()
        layout.setSpacing(8)

        # 각 상태별 카드
        self.stat_labels = {}
        for i, status in enumerate(AttendanceStatus.ALL):
            card = QWidget()
            card_layout = QVBoxLayout()
            card_layout.setAlignment(Qt.AlignCenter)
            card_layout.setSpacing(5)

            # 숫자 (흰색)
            count_label = QLabel("0")
            count_label.setFont(QFont("", 20, QFont.Bold))
            count_label.setStyleSheet("color: white;")
            count_label.setAlignment(Qt.AlignCenter)
            self.stat_labels[status] = count_label

            # 라벨 (흰색, 볼드)
            name_label = QLabel(status)
            name_label.setFont(QFont("", 11, QFont.Bold))
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setStyleSheet("color: white;")

            card_layout.addWidget(count_label)
            card_layout.addWidget(name_label)
            card.setLayout(card_layout)

            # 배경색 비비드하게 (60% 불투명도) + 테두리
            card.setStyleSheet(f"""
                QWidget {{
                    background-color: {AttendanceStatus.COLORS[status]};
                    border: 2px solid {AttendanceStatus.COLORS[status]};
                    border-radius: 8px;
                    padding: 15px;
                    min-width: 95px;
                }}
            """)

            layout.addWidget(card, 0, i)

        group.setLayout(layout)
        return group

    def create_monthly_summary(self):
        """월별 출석률 요약 생성"""
        self.monthly_group = QGroupBox("📆 월별 출석률 요약")
        layout = QVBoxLayout()

        # 요약 테이블을 담을 컨테이너
        self.monthly_container = QWidget()
        self.monthly_layout = QGridLayout()
        self.monthly_layout.setSpacing(8)
        self.monthly_container.setLayout(self.monthly_layout)

        layout.addWidget(self.monthly_container)

        # 안내 메시지
        info = QLabel("💡 과거 달과 현재 진행 중인 달의 출석률을 표시합니다")
        info.setFont(QFont("", 9))
        info.setStyleSheet("color: #64748b; padding: 5px;")
        layout.addWidget(info)

        self.monthly_group.setLayout(layout)
        return self.monthly_group

    def create_calendar(self):
        """캘린더 생성"""
        group = QGroupBox("📅 출석 캘린더")
        layout = QVBoxLayout()

        # 캘린더 위젯
        self.calendar = QCalendarWidget()
        self.calendar.setFont(QFont("", 10))
        self.calendar.setGridVisible(True)
        self.calendar.clicked.connect(self.on_date_clicked)

        # 왼쪽 주차 번호 숨기기
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)

        # 캘린더 스타일
        self.calendar.setStyleSheet("""
            QCalendarWidget QTableView {
                selection-background-color: #10b981;
            }
        """)

        layout.addWidget(self.calendar)

        # 설명
        info = QLabel("💡 평일 날짜를 클릭하여 출결 상태를 변경하세요")
        info.setFont(QFont("", 9))
        info.setStyleSheet("color: #64748b; padding: 5px;")
        layout.addWidget(info)

        group.setLayout(layout)
        return group

    def initialize_data(self):
        """데이터 초기화 (평일은 모두 출석으로)"""
        self.attendance_data.clear()
        current = self.start_date

        while current <= self.end_date:
            # 평일만 (월~금)
            if current.dayOfWeek() in [1, 2, 3, 4, 5]:
                date_str = current.toString("yyyy-MM-dd")
                self.attendance_data[date_str] = AttendanceStatus.PRESENT
            current = current.addDays(1)

    def on_date_clicked(self, qdate):
        """날짜 클릭 이벤트"""
        date_str = qdate.toString("yyyy-MM-dd")

        # 평일인지 확인
        if qdate.dayOfWeek() not in [1, 2, 3, 4, 5]:
            QMessageBox.information(self, "주말", "주말은 출결 처리를 할 수 없습니다.")
            return

        # 현재 상태
        current_status = self.attendance_data.get(date_str, AttendanceStatus.PRESENT)

        # 다이얼로그 표시
        dialog = StatusDialog(current_status, qdate.toString("yyyy년 M월 d일"), self)
        if dialog.exec_() == QDialog.Accepted:
            new_status = dialog.get_status()
            self.attendance_data[date_str] = new_status
            self.update_display()
            self.highlight_calendar_dates()

    def on_start_date_changed(self, qdate):
        """시작일 변경 이벤트"""
        self.start_date = qdate
        self.end_date = qdate.addMonths(1)
        self.initialize_data()
        self.update_display()
        self.highlight_calendar_dates()

    def on_target_changed(self, text):
        """목표 출석률 변경"""
        self.target_rate = int(text.replace("%", ""))
        self.update_display()

    def update_display(self):
        """화면 업데이트"""
        # 기간 표시
        period_text = f"단위기간: {self.start_date.toString('yyyy-MM-dd')} ~ {self.end_date.toString('yyyy-MM-dd')}"
        self.period_label.setText(period_text)

        # 출석률 계산
        total_weekdays = AttendanceCalculator.count_weekdays(self.start_date, self.end_date)
        result = AttendanceCalculator.calculate(self.attendance_data, total_weekdays)

        # 출석률 표시
        rate = result['rate']
        self.rate_label.setText(f"{rate:.1f}%")

        # 색상 변경
        if rate >= 90:
            color = "#10b981"
        elif rate >= 80:
            color = "#f59e0b"
        else:
            color = "#ef4444"
        self.rate_label.setStyleSheet(f"color: {color};")

        # 통계 카드 업데이트
        counts = result['counts']
        for status, label in self.stat_labels.items():
            label.setText(str(counts.get(status, 0)))

        # 월별 요약 업데이트
        self.update_monthly_summary()

        # 캘린더 하이라이트
        self.highlight_calendar_dates()

    def update_monthly_summary(self):
        """월별 출석률 요약 업데이트"""
        # 기존 위젯 제거
        while self.monthly_layout.count():
            item = self.monthly_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 월별 요약 데이터 계산
        monthly_data = AttendanceCalculator.calculate_monthly_summary(
            self.attendance_data,
            self.start_date
        )

        # 데이터가 없으면 안내 메시지 표시
        if len(monthly_data) == 0:
            no_data_label = QLabel("📭 표시할 과거 월 데이터가 없습니다")
            no_data_label.setFont(QFont("", 11))
            no_data_label.setStyleSheet("color: #94a3b8; padding: 20px;")
            no_data_label.setAlignment(Qt.AlignCenter)
            self.monthly_layout.addWidget(no_data_label, 0, 0, 1, -1)
            return

        # 각 월별로 카드 생성
        for i, month_info in enumerate(monthly_data):
            is_current = month_info.get('is_current', False)

            card = QWidget()
            card_layout = QVBoxLayout()
            card_layout.setSpacing(3 if is_current else 5)
            card_layout.setAlignment(Qt.AlignCenter)

            # 월 표시 (현재 월이면 "(진행중)" 추가)
            month_text = month_info['month']
            if is_current:
                month_text += " (진행중)"
            month_label = QLabel(month_text)
            month_label.setFont(QFont("", 9 if is_current else 12, QFont.Bold))
            month_label.setAlignment(Qt.AlignCenter)
            month_label.setStyleSheet("color: #1e293b;")

            # 출석률 표시
            rate = month_info['rate']
            rate_label = QLabel(f"{rate:.1f}%")
            rate_label.setFont(QFont("", 14 if is_current else 18, QFont.Bold))
            rate_label.setAlignment(Qt.AlignCenter)

            # 출석률에 따른 색상
            if rate >= 90:
                rate_color = "#10b981"
            elif rate >= 80:
                rate_color = "#f59e0b"
            else:
                rate_color = "#ef4444"
            rate_label.setStyleSheet(f"color: {rate_color};")

            # 평일 수 표시
            weekdays_label = QLabel(f"평일: {month_info['weekdays']}일")
            weekdays_label.setFont(QFont("", 7 if is_current else 9))
            weekdays_label.setAlignment(Qt.AlignCenter)
            weekdays_label.setStyleSheet("color: #64748b;")

            # 결석 수 표시 (counts에서)
            counts = month_info['counts']
            absent_count = counts.get(AttendanceStatus.ABSENT, 0)
            late_count = counts.get(AttendanceStatus.LATE, 0)
            early_count = counts.get(AttendanceStatus.EARLY, 0)

            details_text = f"결석: {absent_count} | 지각: {late_count} | 조퇴: {early_count}"
            details_label = QLabel(details_text)
            details_label.setFont(QFont("", 7 if is_current else 8))
            details_label.setAlignment(Qt.AlignCenter)
            details_label.setStyleSheet("color: #64748b;")

            card_layout.addWidget(month_label)
            card_layout.addWidget(rate_label)
            card_layout.addWidget(weekdays_label)
            card_layout.addWidget(details_label)

            card.setLayout(card_layout)

            # 카드 스타일 (현재 월은 작게, 반투명 배경)
            if is_current:
                card.setStyleSheet("""
                    QWidget {
                        background-color: #f1f5f9;
                        border: 2px solid #cbd5e1;
                        border-radius: 6px;
                        padding: 8px;
                        min-width: 100px;
                    }
                """)
            else:
                card.setStyleSheet("""
                    QWidget {
                        background-color: white;
                        border: 2px solid #e2e8f0;
                        border-radius: 8px;
                        padding: 12px;
                        min-width: 140px;
                    }
                """)

            # 그리드에 배치 (한 줄에 최대 5개)
            row = i // 5
            col = i % 5
            self.monthly_layout.addWidget(card, row, col)

    def highlight_calendar_dates(self):
        """캘린더에 색상 표시"""
        # QCalendarWidget은 기본적으로 날짜별 색상을 직접 지정하기 어려움
        # 대신 텍스트 포맷을 사용
        for date_str, status in self.attendance_data.items():
            qdate = QDate.fromString(date_str, "yyyy-MM-dd")
            color = QColor(AttendanceStatus.COLORS[status])

            # 텍스트 포맷 설정
            text_format = self.calendar.dateTextFormat(qdate)
            text_format.setBackground(color)
            text_format.setForeground(QColor("white"))
            self.calendar.setDateTextFormat(qdate, text_format)


# ============================================
# 메인 실행
# ============================================
def main():
    app = QApplication(sys.argv)

    # 한글 폰트 설정
    app.setFont(QFont("맑은 고딕", 10))

    window = AttendanceMainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
