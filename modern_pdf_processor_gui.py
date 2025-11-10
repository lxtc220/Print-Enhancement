import sys
import os
import io
import threading
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QFileDialog, QMessageBox, 
                             QProgressBar, QSlider, QCheckBox, QRadioButton, QButtonGroup,
                             QSpinBox, QDoubleSpinBox, QGroupBox, QGridLayout, QSplitter,
                             QScrollArea, QSizePolicy, QLineEdit, QTabWidget, QComboBox,
                             QToolButton, QStyle, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF, QSize
from PyQt6.QtGui import QPixmap, QImage, QPainter, QWheelEvent, QMouseEvent, QPen, QBrush, QIcon, QFont, QPalette
import fitz  # PyMuPDF
import numpy as np
from PIL import Image

# 增加PIL的图像大小限制，以处理大PDF文件
Image.MAX_IMAGE_PIXELS = None  # 移除限制，或者设置为一个更大的值


class ZoomableCanvas(QScrollArea):
    """支持缩放和拖拽的画布，不与其他画布同步"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 创建图像显示标签
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWidget(self.image_label)
        
        # 图像相关
        self.image = None
        self.pixmap = None
        
        # 缩放和拖拽相关
        self.scale = 1.0
        self.min_scale = 0.1
        self.max_scale = 5.0
        self.drag_start_pos = QPointF()
        self.dragging = False
        
        # 设置滚动区域
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 设置样式
        self.setStyleSheet("""
            QScrollArea {
                border: 1px solid #cccccc;
                background-color: #f9f9f9;
                border-radius: 5px;
            }
        """)
        
        # 重置视图
        self.reset_view()
    
    def set_image(self, image, reset_view=True):
        """设置图像"""
        self.image = image.copy()
        if reset_view:
            self.reset_view()
        self.update_display()
    
    def reset_view(self):
        """重置视图"""
        self.scale = 1.0
        
        # 计算适合窗口的缩放比例
        if self.image:
            viewport_width = self.viewport().width()
            viewport_height = self.viewport().height()
            
            if viewport_width > 1 and viewport_height > 1:  # 确保窗口已初始化
                img_width, img_height = self.image.size
                scale_x = viewport_width / img_width
                scale_y = viewport_height / img_height
                self.scale = min(scale_x, scale_y, 1.0)  # 不超过1.0，避免放大
    
    def update_display(self):
        """更新显示"""
        if not self.image:
            self.image_label.clear()
            return
            
        # 计算显示尺寸
        img_width, img_height = self.image.size
        display_width = int(img_width * self.scale)
        display_height = int(img_height * self.scale)
        
        # 调整图像大小
        resized_image = self.image.resize((display_width, display_height), Image.Resampling.LANCZOS)
        
        # 转换为QPixmap - 修复图像格式问题
        if resized_image.mode == 'RGB':
            q_image = QImage(resized_image.tobytes(), display_width, display_height, 
                             display_width * 3, QImage.Format.Format_RGB888)
        elif resized_image.mode == 'RGBA':
            q_image = QImage(resized_image.tobytes(), display_width, display_height, 
                             display_width * 4, QImage.Format.Format_RGBA8888)
        elif resized_image.mode == 'L':  # 灰度图像
            q_image = QImage(resized_image.tobytes(), display_width, display_height, 
                             display_width, QImage.Format.Format_Grayscale8)
        else:
            # 其他格式，转换为RGB
            rgb_image = resized_image.convert('RGB')
            q_image = QImage(rgb_image.tobytes(), display_width, display_height, 
                             display_width * 3, QImage.Format.Format_RGB888)
        
        self.pixmap = QPixmap.fromImage(q_image)
        
        # 显示图像
        self.image_label.setPixmap(self.pixmap)
        self.image_label.resize(display_width, display_height)
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.position()
            self.dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.dragging and self.image:
            # 计算移动距离
            dx = event.position().x() - self.drag_start_pos.x()
            dy = event.position().y() - self.drag_start_pos.y()
            
            # 水平滚动
            h_scroll = self.horizontalScrollBar()
            h_scroll.setValue(h_scroll.value() - int(dx))
            
            # 垂直滚动
            v_scroll = self.verticalScrollBar()
            v_scroll.setValue(v_scroll.value() - int(dy))
            
            # 更新起始位置
            self.drag_start_pos = event.position()
    
    def wheelEvent(self, event):
        """鼠标滚轮事件"""
        if not self.image:
            return
            
        # 确定缩放方向
        if event.angleDelta().y() > 0:
            scale_factor = 1.1
        else:
            scale_factor = 0.9
        
        # 计算新的缩放比例
        new_scale = self.scale * scale_factor
        new_scale = max(self.min_scale, min(new_scale, self.max_scale))
        
        # 计算缩放中心点
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        
        # 调整视图位置以保持鼠标位置不变
        if viewport_width > 0 and viewport_height > 0:
            # 获取鼠标在视口中的位置
            mouse_pos = event.position()
            
            # 获取当前滚动位置
            h_scroll = self.horizontalScrollBar()
            v_scroll = self.verticalScrollBar()
            scroll_x = h_scroll.value()
            scroll_y = v_scroll.value()
            
            # 计算鼠标相对于图像的位置
            rel_x = mouse_pos.x() + scroll_x
            rel_y = mouse_pos.y() + scroll_y
            
            # 计算新的滚动位置
            new_scroll_x = rel_x * (new_scale / self.scale) - mouse_pos.x()
            new_scroll_y = rel_y * (new_scale / self.scale) - mouse_pos.y()
            
            # 记录缩放变化
            self.scale = new_scale
            
            # 更新显示
            self.update_display()
            
            # 设置新的滚动位置
            h_scroll.setValue(int(new_scroll_x))
            v_scroll.setValue(int(new_scroll_y))
    
    def zoom_in(self):
        """放大"""
        if not self.image:
            return
            
        new_scale = self.scale * 1.2
        new_scale = min(new_scale, self.max_scale)
        self.scale = new_scale
        self.update_display()
    
    def zoom_out(self):
        """缩小"""
        if not self.image:
            return
            
        new_scale = self.scale / 1.2
        new_scale = max(new_scale, self.min_scale)
        self.scale = new_scale
        self.update_display()
    
    def fit_to_window(self):
        """适应窗口"""
        if not self.image:
            return
            
        self.reset_view()
        self.update_display()


class ImageProcessingThread(QThread):
    """图像处理线程"""
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self, pdf_path, output_path, current_page, red_weight, green_weight, blue_weight, 
                 black_intensity, compression_quality, output_format, use_compression):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_path = output_path
        self.current_page = current_page
        self.red_weight = red_weight
        self.green_weight = green_weight
        self.blue_weight = blue_weight
        self.black_intensity = black_intensity
        self.compression_quality = compression_quality
        self.output_format = output_format
        self.use_compression = use_compression
    
    def run(self):
        try:
            # 打开PDF文件
            pdf_document = fitz.open(self.pdf_path)
            
            # 创建新的PDF文档
            new_pdf = fitz.open()
            
            # 处理每一页
            total_pages = len(pdf_document)
            for page_num in range(total_pages):
                # 更新进度
                progress = int((page_num / total_pages) * 100)
                self.progress_signal.emit(progress)
                
                # 获取页面
                page = pdf_document[page_num]
                
                # 渲染页面为图像
                mat = fitz.Matrix(3.0, 3.0)  # 高分辨率
                pix = page.get_pixmap(matrix=mat)
                
                # 转换为PIL图像
                img_data = pix.tobytes("ppm")
                pil_image = Image.open(io.BytesIO(img_data))
                
                # 转换为numpy数组
                img_array = np.array(pil_image)
                
                # 如果是RGBA图像，转换为RGB
                if len(img_array.shape) == 3 and img_array.shape[2] == 4:
                    img_array = img_array[:, :, :3]
                
                # 应用自定义权重
                if len(img_array.shape) == 3 and img_array.shape[2] >= 3:
                    # 归一化权重
                    total_weight = self.red_weight + self.green_weight + self.blue_weight
                    if total_weight > 0:
                        r_weight = self.red_weight / total_weight
                        g_weight = self.green_weight / total_weight
                        b_weight = self.blue_weight / total_weight
                    else:
                        r_weight = g_weight = b_weight = 1/3
                    
                    # 创建加权灰度图像
                    gray_img = np.zeros_like(img_array[:, :, 0])
                    gray_img = img_array[:, :, 0] * r_weight + \
                              img_array[:, :, 1] * g_weight + \
                              img_array[:, :, 2] * b_weight
                    
                    # 应用黑色强度调整 - 使用伽马校正而不是线性缩放
                    gray_img = gray_img.astype(np.float32) / 255.0
                    gamma = 1.0 / (1.0 + self.black_intensity)  # 使用伽马校正
                    corrected = np.power(gray_img, gamma)
                    corrected = np.clip(corrected, 0, 1)
                    gray_img = (corrected * 255).astype(np.uint8)
                    
                    # 转换回PIL图像
                    gray_pil = Image.fromarray(gray_img, mode='L')
                    
                    # 如果原始图像是彩色的，创建一个RGB版本的灰度图像
                    if len(img_array.shape) == 3:
                        rgb_gray = np.stack([gray_img, gray_img, gray_img], axis=2)
                        processed_pil = Image.fromarray(rgb_gray, mode='RGB')
                    else:
                        processed_pil = gray_pil
                else:
                    # 如果不是RGB图像，直接应用黑色强度调整
                    img_array = img_array.astype(np.float32) / 255.0
                    gamma = 1.0 / (1.0 + self.black_intensity)
                    corrected = np.power(img_array, gamma)
                    corrected = np.clip(corrected, 0, 1)
                    adjusted_img = (corrected * 255).astype(np.uint8)
                    processed_pil = Image.fromarray(adjusted_img)
                
                # 将处理后的图像转换回PDF页面
                img_buffer = io.BytesIO()
                
                # 根据压缩开关状态决定是否应用压缩
                if self.use_compression:
                    # 启用压缩
                    if self.output_format.lower() == 'jpeg':
                        processed_pil.save(img_buffer, format='JPEG', quality=self.compression_quality)
                    elif self.output_format.lower() == 'png':
                        processed_pil.save(img_buffer, format='PNG', optimize=True)
                    elif self.output_format.lower() == 'webp':
                        processed_pil.save(img_buffer, format='WEBP', quality=self.compression_quality)
                    else:
                        processed_pil.save(img_buffer, format='JPEG', quality=self.compression_quality)
                else:
                    # 不启用压缩
                    if self.output_format.lower() == 'jpeg':
                        processed_pil.save(img_buffer, format='JPEG', quality=95)  # 高质量
                    elif self.output_format.lower() == 'png':
                        processed_pil.save(img_buffer, format='PNG', optimize=False)  # 不优化
                    elif self.output_format.lower() == 'webp':
                        processed_pil.save(img_buffer, format='WEBP', quality=95)  # 高质量
                    else:
                        processed_pil.save(img_buffer, format='JPEG', quality=95)  # 高质量
                
                # 创建新的PDF页面
                img_rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
                new_page = new_pdf.new_page(width=page.rect.width, height=page.rect.height)
                new_page.insert_image(img_rect, stream=img_buffer.getvalue())
            
            # 保存处理后的PDF
            new_pdf.save(self.output_path)
            new_pdf.close()
            pdf_document.close()
            
            # 发送完成信号
            self.finished_signal.emit(f"PDF处理完成，已保存到: {self.output_path}")
            
        except Exception as e:
            # 发送错误信号
            self.error_signal.emit(f"处理过程中出错: {str(e)}")


class ModernPDFProcessorGUI(QMainWindow):
    """现代化的PDF处理器GUI"""
    def __init__(self):
        super().__init__()
        
        # 初始化变量
        self.pdf_path = ""
        self.output_path = ""
        self.current_page = 1
        self.total_pages = 0
        
        # 默认参数值
        self.red_weight = 0.299
        self.green_weight = 0.587
        self.blue_weight = 0.114
        self.black_intensity = -0.5  # 伽马校正默认值改为-0.5
        self.compression_quality = 85
        self.output_format = 'JPEG'
        self.use_compression = False  # 压缩默认关闭
        
        # 处理线程
        self.processing_thread = None
        
        # 设置窗口
        self.setWindowTitle("高级PDF处理器 - 现代化界面")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置应用样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: white;
                border-radius: 5px;
            }
            QTabBar::tab {
                background: #e0e0e0;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #4CAF50;
                color: white;
            }
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: white;
                height: 10px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
        """)
        
        # 初始化UI
        self.init_ui()
        
        # 默认应用标准灰度预设
        self.set_gray_preset()
    
    def init_ui(self):
        """初始化用户界面"""
        # 主窗口部件
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 文件选择选项卡
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        
        # 创建一个水平分割器用于上下布局
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 上方控制面板
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        
        # 文件选择组
        file_group = QGroupBox("文件选择")
        file_group_layout = QGridLayout(file_group)
        
        file_group_layout.addWidget(QLabel("输入PDF:"), 0, 0)
        self.pdf_path_edit = QLineEdit()
        self.pdf_path_edit.setReadOnly(True)
        file_group_layout.addWidget(self.pdf_path_edit, 0, 1)
        
        browse_input_btn = QPushButton("浏览...")
        browse_input_btn.clicked.connect(self.browse_input_pdf)
        file_group_layout.addWidget(browse_input_btn, 0, 2)
        
        file_group_layout.addWidget(QLabel("输出PDF:"), 1, 0)
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setReadOnly(True)
        file_group_layout.addWidget(self.output_path_edit, 1, 1)
        
        browse_output_btn = QPushButton("浏览...")
        browse_output_btn.clicked.connect(self.browse_output_pdf)
        file_group_layout.addWidget(browse_output_btn, 1, 2)
        
        control_layout.addWidget(file_group)
        
        # 参数预设和黑色强度控制组 - 移到文件与预览页面
        param_group = QGroupBox("参数设置")
        param_layout = QGridLayout(param_group)
        
        # 黑色强度行
        black_container = QWidget()
        black_layout = QHBoxLayout(black_container)
        black_layout.setContentsMargins(0, 0, 0, 0)
        black_layout.addWidget(QLabel("伽马校正:"))
        self.black_slider = QSlider(Qt.Orientation.Horizontal)
        self.black_slider.setMinimum(-100)
        self.black_slider.setMaximum(100)
        self.black_slider.setValue(int(self.black_intensity * 100))
        self.black_slider.valueChanged.connect(lambda v: self.on_slider_changed(v, "black_intensity", 0.01))
        black_layout.addWidget(self.black_slider)
        self.black_spinbox = QDoubleSpinBox()
        self.black_spinbox.setMinimum(-1.0)
        self.black_spinbox.setMaximum(1.0)
        self.black_spinbox.setSingleStep(0.01)
        self.black_spinbox.setDecimals(2)
        self.black_spinbox.setValue(self.black_intensity)
        self.black_spinbox.variable_name = "black_intensity"
        self.black_spinbox.valueChanged.connect(lambda v: self.on_spinbox_changed(v, "black_intensity", self.black_slider, 0.01))
        black_layout.addWidget(self.black_spinbox)
        param_layout.addWidget(black_container, 0, 0, 1, 4)
        
        # 添加参数组到控制面板
        control_layout.addWidget(param_group)
        
        # 页面导航
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        
        nav_layout.addWidget(QLabel("页面:"))
        self.current_page_spin = QSpinBox()
        self.current_page_spin.setMinimum(1)
        self.current_page_spin.setValue(1)
        self.current_page_spin.valueChanged.connect(self.on_page_changed)
        nav_layout.addWidget(self.current_page_spin)
        
        self.total_pages_label = QLabel("/ 0")
        nav_layout.addWidget(self.total_pages_label)
        
        prev_btn = QPushButton("上一页")
        prev_btn.clicked.connect(self.prev_page)
        nav_layout.addWidget(prev_btn)
        
        next_btn = QPushButton("下一页")
        next_btn.clicked.connect(self.next_page)
        nav_layout.addWidget(next_btn)
        
        update_preview_btn = QPushButton("更新预览")
        update_preview_btn.clicked.connect(self.update_preview)
        nav_layout.addWidget(update_preview_btn)
        
        process_btn = QPushButton("处理PDF")
        process_btn.clicked.connect(self.process_pdf)
        nav_layout.addWidget(process_btn)
        
        nav_layout.addStretch()
        control_layout.addWidget(nav_widget)
        
        # 预览区域
        preview_widget = QWidget()
        preview_layout = QHBoxLayout(preview_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 原始图像预览
        original_widget = QWidget()
        original_layout = QVBoxLayout(original_widget)
        
        original_layout.addWidget(QLabel("原始图像"))
        
        # 创建可缩放画布
        self.original_canvas = ZoomableCanvas()
        original_layout.addWidget(self.original_canvas)
        
        # 原始图像控制按钮
        original_controls = QHBoxLayout()
        
        zoom_in_original_btn = QPushButton("放大")
        zoom_in_original_btn.clicked.connect(self.original_canvas.zoom_in)
        original_controls.addWidget(zoom_in_original_btn)
        
        zoom_out_original_btn = QPushButton("缩小")
        zoom_out_original_btn.clicked.connect(self.original_canvas.zoom_out)
        original_controls.addWidget(zoom_out_original_btn)
        
        # 添加重置按钮
        reset_original_btn = QPushButton("重置视图")
        reset_original_btn.clicked.connect(self.original_canvas.reset_view)
        original_controls.addWidget(reset_original_btn)
        
        original_controls.addStretch()
        original_layout.addLayout(original_controls)
        
        splitter.addWidget(original_widget)
        
        # 处理后图像预览
        processed_widget = QWidget()
        processed_layout = QVBoxLayout(processed_widget)
        
        processed_layout.addWidget(QLabel("处理后图像"))
        
        # 创建可缩放画布
        self.processed_canvas = ZoomableCanvas()
        processed_layout.addWidget(self.processed_canvas)
        
        # 处理后图像控制按钮
        processed_controls = QHBoxLayout()
        
        zoom_in_processed_btn = QPushButton("放大")
        zoom_in_processed_btn.clicked.connect(self.processed_canvas.zoom_in)
        processed_controls.addWidget(zoom_in_processed_btn)
        
        zoom_out_processed_btn = QPushButton("缩小")
        zoom_out_processed_btn.clicked.connect(self.processed_canvas.zoom_out)
        processed_controls.addWidget(zoom_out_processed_btn)
        
        reset_processed_btn = QPushButton("重置")
        reset_processed_btn.clicked.connect(self.processed_canvas.reset_view)
        processed_controls.addWidget(reset_processed_btn)
        
        processed_controls.addStretch()
        processed_layout.addLayout(processed_controls)
        
        splitter.addWidget(processed_widget)
        
        # 设置分割器比例
        splitter.setSizes([400, 400])
        
        preview_layout.addWidget(splitter)
        
        # 添加控制面板和预览区域到分割器
        main_splitter.addWidget(control_widget)
        main_splitter.addWidget(preview_widget)
        
        # 设置分割器比例
        main_splitter.setSizes([200, 600])
        
        # 添加分割器到文件选项卡
        file_layout.addWidget(main_splitter)
        
        # 颜色权重行
        param_tab = QWidget()
        param_layout = QVBoxLayout(param_tab)
        
        # 颜色权重组
        color_group = QGroupBox("颜色权重")
        color_layout = QGridLayout(color_group)
        
        # 颜色权重行
        color_layout.addWidget(QLabel("颜色权重:"), 0, 0)
        
        # 红色权重
        red_container = QWidget()
        red_layout = QHBoxLayout(red_container)
        red_layout.setContentsMargins(0, 0, 0, 0)
        red_layout.addWidget(QLabel("红:"))
        self.red_slider = QSlider(Qt.Orientation.Horizontal)
        self.red_slider.setMinimum(0)
        self.red_slider.setMaximum(1000)
        self.red_slider.setValue(int(self.red_weight * 1000))
        self.red_slider.valueChanged.connect(lambda v: self.on_slider_changed(v, "red_weight", 0.001))
        red_layout.addWidget(self.red_slider)
        self.red_spinbox = QDoubleSpinBox()
        self.red_spinbox.setMinimum(0.0)
        self.red_spinbox.setMaximum(1.0)
        self.red_spinbox.setSingleStep(0.001)
        self.red_spinbox.setDecimals(3)
        self.red_spinbox.setValue(self.red_weight)
        self.red_spinbox.variable_name = "red_weight"
        self.red_spinbox.valueChanged.connect(lambda v: self.on_spinbox_changed(v, "red_weight", self.red_slider, 0.001))
        red_layout.addWidget(self.red_spinbox)
        color_layout.addWidget(red_container, 0, 1)
        
        # 绿色权重
        green_container = QWidget()
        green_layout = QHBoxLayout(green_container)
        green_layout.setContentsMargins(0, 0, 0, 0)
        green_layout.addWidget(QLabel("绿:"))
        self.green_slider = QSlider(Qt.Orientation.Horizontal)
        self.green_slider.setMinimum(0)
        self.green_slider.setMaximum(1000)
        self.green_slider.setValue(int(self.green_weight * 1000))
        self.green_slider.valueChanged.connect(lambda v: self.on_slider_changed(v, "green_weight", 0.001))
        green_layout.addWidget(self.green_slider)
        self.green_spinbox = QDoubleSpinBox()
        self.green_spinbox.setMinimum(0.0)
        self.green_spinbox.setMaximum(1.0)
        self.green_spinbox.setSingleStep(0.001)
        self.green_spinbox.setDecimals(3)
        self.green_spinbox.setValue(self.green_weight)
        self.green_spinbox.variable_name = "green_weight"
        self.green_spinbox.valueChanged.connect(lambda v: self.on_spinbox_changed(v, "green_weight", self.green_slider, 0.001))
        green_layout.addWidget(self.green_spinbox)
        color_layout.addWidget(green_container, 0, 2)
        
        # 蓝色权重
        blue_container = QWidget()
        blue_layout = QHBoxLayout(blue_container)
        blue_layout.setContentsMargins(0, 0, 0, 0)
        blue_layout.addWidget(QLabel("蓝:"))
        self.blue_slider = QSlider(Qt.Orientation.Horizontal)
        self.blue_slider.setMinimum(0)
        self.blue_slider.setMaximum(1000)
        self.blue_slider.setValue(int(self.blue_weight * 1000))
        self.blue_slider.valueChanged.connect(lambda v: self.on_slider_changed(v, "blue_weight", 0.001))
        blue_layout.addWidget(self.blue_slider)
        self.blue_spinbox = QDoubleSpinBox()
        self.blue_spinbox.setMinimum(0.0)
        self.blue_spinbox.setMaximum(1.0)
        self.blue_spinbox.setSingleStep(0.001)
        self.blue_spinbox.setDecimals(3)
        self.blue_spinbox.setValue(self.blue_weight)
        self.blue_spinbox.variable_name = "blue_weight"
        self.blue_spinbox.valueChanged.connect(lambda v: self.on_spinbox_changed(v, "blue_weight", self.blue_slider, 0.001))
        blue_layout.addWidget(self.blue_spinbox)
        color_layout.addWidget(blue_container, 0, 3)
        
        # 预设按钮行
        preset_container = QWidget()
        preset_layout = QHBoxLayout(preset_container)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        
        preset_layout.addWidget(QLabel("预设:"))
        
        gray_preset_btn = QPushButton("标准灰度")
        gray_preset_btn.setMaximumWidth(80)
        gray_preset_btn.clicked.connect(self.set_gray_preset)
        preset_layout.addWidget(gray_preset_btn)
        
        sepia_preset_btn = QPushButton("复古")
        sepia_preset_btn.setMaximumWidth(60)
        sepia_preset_btn.clicked.connect(self.set_sepia_preset)
        preset_layout.addWidget(sepia_preset_btn)
        
        blue_preset_btn = QPushButton("蓝调")
        blue_preset_btn.setMaximumWidth(60)
        blue_preset_btn.clicked.connect(self.set_blue_preset)
        preset_layout.addWidget(blue_preset_btn)
        
        yellow_preset_btn = QPushButton("加强黄色")
        yellow_preset_btn.setMaximumWidth(80)
        yellow_preset_btn.clicked.connect(self.set_yellow_preset)
        preset_layout.addWidget(yellow_preset_btn)
        
        preset_layout.addStretch()
        color_layout.addWidget(preset_container, 1, 0, 1, 4)
        
        param_layout.addWidget(color_group)
        
        # 输出设置组
        output_group = QGroupBox("输出设置")
        output_layout = QGridLayout(output_group)
        
        # 输出格式
        output_layout.addWidget(QLabel("输出格式:"), 0, 0)
        
        format_combo = QComboBox()
        format_combo.addItems(["JPEG", "PNG", "WEBP"])
        format_combo.setCurrentText(self.output_format)
        format_combo.currentTextChanged.connect(self.on_format_changed)
        output_layout.addWidget(format_combo, 0, 1)
        
        # 启用压缩复选框
        self.enable_compression_checkbox = QCheckBox("启用压缩")
        self.enable_compression_checkbox.setChecked(True)  # 默认启用压缩
        self.enable_compression_checkbox.stateChanged.connect(self.on_compression_toggled)
        output_layout.addWidget(self.enable_compression_checkbox, 1, 0)
        
        # 压缩质量
        self.create_parameter_control(output_layout, 2, "压缩质量:", "compression_quality", 10, 100, 1)
        
        param_layout.addWidget(output_group)
        
        # 添加文件选项卡到选项卡控件
        tab_widget.addTab(file_tab, "文件与预览")
        
        # 添加参数选项卡到选项卡控件
        tab_widget.addTab(param_tab, "输出设置")
        
        # 添加选项卡到主布局
        main_layout.addWidget(tab_widget, 1)  # 1表示拉伸权重
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        main_layout.addWidget(self.status_label)
        
        # 设置主窗口部件
        self.setCentralWidget(main_widget)
    
    def create_tool_button(self, text, callback):
        """创建工具按钮"""
        btn = QPushButton(text)
        btn.clicked.connect(callback)
        btn.setMaximumWidth(100)
        return btn
    
    def create_parameter_control(self, layout, row, label_text, variable_name, min_val, max_val, resolution):
        """创建参数控制（滑块+输入框）"""
        # 标签
        layout.addWidget(QLabel(label_text), row, 0)
        
        # 滑块和输入框的容器
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # 获取当前变量值
        current_value = getattr(self, variable_name)
        
        # 滑块
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(int(min_val / resolution))
        slider.setMaximum(int(max_val / resolution))
        slider.setValue(int(current_value / resolution))
        slider.valueChanged.connect(lambda value: self.on_slider_changed(value, variable_name, resolution))
        container_layout.addWidget(slider)
        
        # 输入框
        spin_box = QDoubleSpinBox()
        spin_box.setMinimum(min_val)
        spin_box.setMaximum(max_val)
        spin_box.setSingleStep(resolution)
        spin_box.setDecimals(3 if resolution < 0.01 else 2)
        spin_box.setValue(current_value)
        # 存储变量名以便后续识别
        spin_box.variable_name = variable_name
        spin_box.valueChanged.connect(lambda value: self.on_spinbox_changed(value, variable_name, slider, resolution))
        container_layout.addWidget(spin_box)
        
        layout.addWidget(container, row, 1, 1, 2)
    
    def on_slider_changed(self, value, variable_name, resolution):
        """滑块值变化事件"""
        setattr(self, variable_name, value * resolution)
        self.update_preview()
        # 更新对应的spinbox
        self.update_spinbox_value(variable_name, value * resolution)
    
    def on_spinbox_changed(self, value, variable_name, slider, resolution):
        """输入框值变化事件"""
        setattr(self, variable_name, value)
        slider.setValue(int(value / resolution))
        self.update_preview()
    
    def update_spinbox_value(self, variable_name, value):
        """更新指定变量的spinbox值"""
        # 遍历所有控件，找到对应的spinbox并更新
        for widget in self.findChildren(QDoubleSpinBox):
            # 通过检查变量名是否在spinbox的objectName中来确定是否需要更新
            if hasattr(widget, 'variable_name') and widget.variable_name == variable_name:
                widget.setValue(value)
                return
    
    def on_compression_toggled(self, state):
        """压缩开关切换事件"""
        self.use_compression = (state == 2)  # Qt.Checked = 2
        self.update_preview()
        status_text = "已启用压缩" if self.use_compression else "已禁用压缩"
        self.status_label.setText(status_text)
    
    def on_format_changed(self, format_text):
        """格式变化事件"""
        self.output_format = format_text
        self.update_preview()
    
    def on_page_changed(self, value):
        """页面变化事件"""
        self.current_page = value
        self.update_preview()
    
    def set_gray_preset(self):
        """设置标准灰度预设"""
        self.red_weight = 0.299
        self.green_weight = 0.587
        self.blue_weight = 0.114
        
        # 更新滑块和输入框
        self.red_slider.setValue(int(self.red_weight * 1000))
        self.green_slider.setValue(int(self.green_weight * 1000))
        self.blue_slider.setValue(int(self.blue_weight * 1000))
        self.red_spinbox.setValue(self.red_weight)
        self.green_spinbox.setValue(self.green_weight)
        self.blue_spinbox.setValue(self.blue_weight)
        
        self.update_preview()
        self.status_label.setText("已应用标准灰度预设")
    
    def set_sepia_preset(self):
        """设置复古预设"""
        self.red_weight = 0.393
        self.green_weight = 0.769
        self.blue_weight = 0.189
        
        # 更新滑块和输入框
        self.red_slider.setValue(int(self.red_weight * 1000))
        self.green_slider.setValue(int(self.green_weight * 1000))
        self.blue_slider.setValue(int(self.blue_weight * 1000))
        self.red_spinbox.setValue(self.red_weight)
        self.green_spinbox.setValue(self.green_weight)
        self.blue_spinbox.setValue(self.blue_weight)
        
        self.update_preview()
        self.status_label.setText("已应用复古预设")
    
    def set_blue_preset(self):
        """设置蓝调预设"""
        self.red_weight = 0.1
        self.green_weight = 0.3
        self.blue_weight = 0.6
        
        # 更新滑块和输入框
        self.red_slider.setValue(int(self.red_weight * 1000))
        self.green_slider.setValue(int(self.green_weight * 1000))
        self.blue_slider.setValue(int(self.blue_weight * 1000))
        self.red_spinbox.setValue(self.red_weight)
        self.green_spinbox.setValue(self.green_weight)
        self.blue_spinbox.setValue(self.blue_weight)
        
        self.update_preview()
        self.status_label.setText("已应用蓝调预设")
    
    def set_yellow_preset(self):
        """设置加强黄色预设"""
        self.red_weight = 0.5
        self.green_weight = 0.45
        self.blue_weight = 0.05
        
        # 更新滑块和输入框
        self.red_slider.setValue(int(self.red_weight * 1000))
        self.green_slider.setValue(int(self.green_weight * 1000))
        self.blue_slider.setValue(int(self.blue_weight * 1000))
        self.red_spinbox.setValue(self.red_weight)
        self.green_spinbox.setValue(self.green_weight)
        self.blue_spinbox.setValue(self.blue_weight)
        
        self.update_preview()
        self.status_label.setText("已应用加强黄色预设")
    
    def browse_input_pdf(self):
        """浏览输入PDF文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择PDF文件", "", "PDF文件 (*.pdf);;所有文件 (*.*)"
        )
        if filename:
            self.pdf_path = filename
            self.pdf_path_edit.setText(filename)
            
            # 自动设置输出文件名
            base_name = os.path.splitext(os.path.basename(filename))[0]
            output_dir = os.path.dirname(filename)
            self.output_path = os.path.join(output_dir, f"{base_name}_processed.pdf")
            self.output_path_edit.setText(self.output_path)
            
            # 加载PDF信息
            self.load_pdf_info()
            # 更新预览
            self.update_preview()
    
    def browse_output_pdf(self):
        """浏览输出PDF文件"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "选择输出PDF文件", self.output_path, "PDF文件 (*.pdf);;所有文件 (*.*)"
        )
        if filename:
            self.output_path = filename
            self.output_path_edit.setText(filename)
    
    def load_pdf_info(self):
        """加载PDF信息"""
        if not self.pdf_path:
            return
            
        try:
            pdf_document = fitz.open(self.pdf_path)
            self.total_pages = len(pdf_document)
            self.current_page_spin.setMaximum(self.total_pages)
            self.total_pages_label.setText(f"/ {self.total_pages}")
            pdf_document.close()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开PDF文件: {str(e)}")
    
    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.current_page_spin.setValue(self.current_page)
            self.update_preview()
    
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.current_page_spin.setValue(self.current_page)
            self.update_preview()
    
    def update_preview(self):
        """更新预览"""
        if not self.pdf_path:
            return
            
        try:
            # 打开PDF文件
            pdf_document = fitz.open(self.pdf_path)
            
            # 检查页面范围
            if self.current_page < 1 or self.current_page > len(pdf_document):
                QMessageBox.warning(self, "警告", f"页面号超出范围 (1-{len(pdf_document)})")
                pdf_document.close()
                return
            
            # 获取当前页面
            page = pdf_document[self.current_page - 1]
            
            # 渲染页面为图像
            mat = fitz.Matrix(2.0, 2.0)  # 中等分辨率用于预览
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为PIL图像
            img_data = pix.tobytes("ppm")
            pil_image = Image.open(io.BytesIO(img_data))
            
            # 显示原始图像 - 不重置视图
            self.original_canvas.set_image(pil_image, reset_view=False)
            
            # 应用处理
            processed_image = self.process_image(pil_image)
            
            # 显示处理后图像 - 不重置视图
            self.processed_canvas.set_image(processed_image, reset_view=False)
            
            pdf_document.close()
            
            self.status_label.setText(f"预览已更新 - 第 {self.current_page} 页")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"预览更新失败: {str(e)}")
    
    def process_image(self, pil_image):
        """处理单个图像"""
        # 转换为numpy数组
        img_array = np.array(pil_image)
        
        # 如果是RGBA图像，转换为RGB
        if len(img_array.shape) == 3 and img_array.shape[2] == 4:
            img_array = img_array[:, :, :3]
        
        # 应用自定义权重
        if len(img_array.shape) == 3 and img_array.shape[2] >= 3:
            # 归一化权重
            total_weight = self.red_weight + self.green_weight + self.blue_weight
            if total_weight > 0:
                r_weight = self.red_weight / total_weight
                g_weight = self.green_weight / total_weight
                b_weight = self.blue_weight / total_weight
            else:
                r_weight = g_weight = b_weight = 1/3
            
            # 创建加权灰度图像
            gray_img = np.zeros_like(img_array[:, :, 0])
            gray_img = img_array[:, :, 0] * r_weight + \
                      img_array[:, :, 1] * g_weight + \
                      img_array[:, :, 2] * b_weight
            
            # 应用黑色强度调整 - 使用伽马校正而不是线性缩放
            gray_img = gray_img.astype(np.float32) / 255.0
            gamma = 1.0 / (1.0 + self.black_intensity)  # 使用伽马校正
            corrected = np.power(gray_img, gamma)
            corrected = np.clip(corrected, 0, 1)
            gray_img = (corrected * 255).astype(np.uint8)
            
            # 转换回PIL图像
            gray_pil = Image.fromarray(gray_img, mode='L')
            
            # 如果原始图像是彩色的，创建一个RGB版本的灰度图像
            if len(img_array.shape) == 3:
                rgb_gray = np.stack([gray_img, gray_img, gray_img], axis=2)
                processed_pil = Image.fromarray(rgb_gray, mode='RGB')
            else:
                processed_pil = gray_pil
        else:
            # 如果不是RGB图像，直接应用黑色强度调整
            img_array = img_array.astype(np.float32) / 255.0
            gamma = 1.0 / (1.0 + self.black_intensity)
            corrected = np.power(img_array, gamma)
            corrected = np.clip(corrected, 0, 1)
            adjusted_img = (corrected * 255).astype(np.uint8)
            processed_pil = Image.fromarray(adjusted_img)
        
        return processed_pil
    
    def process_pdf(self):
        """处理PDF"""
        if not self.pdf_path:
            QMessageBox.warning(self, "警告", "请先选择输入PDF文件")
            return
                
        if not self.output_path:
            QMessageBox.warning(self, "警告", "请先选择输出PDF文件")
            return
        
        # 禁用处理按钮，显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("开始处理PDF...")
        
        # 创建处理线程
        self.processing_thread = ImageProcessingThread(
            self.pdf_path, self.output_path, self.current_page,
            self.red_weight, self.green_weight, self.blue_weight,
            self.black_intensity, self.compression_quality, self.output_format, self.use_compression
        )
        
        # 连接信号
        self.processing_thread.progress_signal.connect(self.update_progress)
        self.processing_thread.finished_signal.connect(self.processing_finished)
        self.processing_thread.error_signal.connect(self.processing_error)
        
        # 启动线程
        self.processing_thread.start()
    
    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
        self.status_label.setText(f"处理中... {value}%")
    
    def processing_finished(self, message):
        """处理完成"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)
        QMessageBox.information(self, "完成", message)
    
    def processing_error(self, error_message):
        """处理错误"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("处理出错")
        QMessageBox.critical(self, "错误", error_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 创建主窗口
    window = ModernPDFProcessorGUI()
    window.show()
    
    sys.exit(app.exec())