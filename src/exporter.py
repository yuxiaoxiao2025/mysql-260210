import pandas as pd
import os
from datetime import datetime

class ExcelExporter:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def export(self, df, filename=None, sheet_name="Sheet1"):
        """
        导出 DataFrame 到 Excel 并美化
        :param df: pandas DataFrame
        :param filename: 文件名 (如果不带扩展名会自动补上 .xlsx)
        :param sheet_name: sheet 名称
        :return: 导出文件的完整路径
        """
        if filename is None:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        if not filename.endswith('.xlsx'):
            filename += '.xlsx'
            
        filepath = os.path.join(self.output_dir, filename)
        
        # 使用 XlsxWriter 引擎
        writer = pd.ExcelWriter(filepath, engine='xlsxwriter')
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # 获取 workbook 和 worksheet 对象
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        
        # 定义样式
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # 获取 DataFrame 的维度
        (max_row, max_col) = df.shape
        
        # 设置表头样式
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
        # 自动调整列宽
        for i, col in enumerate(df.columns):
            # 计算该列最大宽度 (表头和内容取最大值)
            column_len = max(
                df[col].astype(str).map(len).max(),
                len(str(col))
            )
            # 限制最大宽度，避免过宽
            column_len = min(column_len + 2, 50) 
            worksheet.set_column(i, i, column_len)
            
        # 冻结首行
        worksheet.freeze_panes(1, 0)
        
        # 启用自动筛选
        worksheet.autofilter(0, 0, max_row, max_col - 1)
        
        writer.close()
        return filepath
