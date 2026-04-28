#!/bin/bash

# 检测前端代码中的硬编码中文文本
# 用法: ./scripts/check-hardcoded-text.sh

echo "正在检测 apps/web/src 中的硬编码中文..."
echo "======================================"

# 查找所有 .tsx 和 .ts 文件
# 排除 public/locales 目录(翻译文件)
# 排除注释行(//)
# 排除已使用 useTranslation 或 t(' 的行
# 查找中文字符范围 [\u4e00-\u9fa5]

# 使用 grep 的 Perl 正则表达式匹配中文字符
find apps/web/src -type f \( -name "*.tsx" -o -name "*.ts" \) ! -path "*/node_modules/*" ! -name "*.d.ts" | while read file; do
  # 检查文件中是否包含中文字符
  # 使用 grep -P (Perl 正则)来匹配中文字符
  result=$(grep -n -P "[\x{4e00}-\x{9fa5}]" "$file" 2>/dev/null | \
    # 排除注释行
    grep -v "^\s*//" | \
    # 排除包含 useTranslation 的行
    grep -v "useTranslation" | \
    # 排除包含 t(' 或 t(" 的行
    grep -vE "t\(['\"]" | \
    # 排除包含 i18n 的行
    grep -v "i18n" | \
    # 排除包含 getLocale 的行
    grep -v "getLocale" | \
    # 排除包含 import 的行(导入语句可能有中文注释)
    grep -v "^\s*import")

  if [ -n "$result" ]; then
    echo ""
    echo "文件: $file"
    echo "$result"
  fi
done

echo ""
echo "======================================"
echo "检测完成"
echo "注意:请手动检查上述结果,排除误报(如字符串模板中的变量等)"
