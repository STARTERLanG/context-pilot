import QtQuick
import QtQuick.Controls

// 只读但可选中 / 可复制的文本块（历史记录正文）。
//
// 为什么不用 Text：Text 只负责渲染，鼠标选不了、Ctrl+C 也复制不到。
// 这里用只读 TextEdit，高度随内容增长（由外层列表滚动），因此不自带 Flickable。
//
// 两个容易踩的点：
// - selectByMouse 打开后，TextEdit 会自己吃掉鼠标事件，外层 TapHandler 就不会
//   在拖选时误触发展开/收起；但这也意味着「点一下正文」不会传出去，
//   调用方不要把可点区域压在正文上。
// - 高度不能用 implicitHeight 之外的方式撑开（anchors 会给它固定高度，
//   内容就会被裁掉），故由内容决定宽度与高度。
TextEdit {
    id: root
    property alias text: root.text
    // 只读：允许选中与复制，但不接受输入
    readOnly: true
    selectByMouse: true
    persistentSelection: true  // 焦点移走后保留选区，方便切到别处再复制
    wrapMode: TextEdit.Wrap
    color: theme.textPrimary
    selectionColor: theme.accent
    selectedTextColor: theme.textInverse
    font.family: theme.fontFamily
    font.pixelSize: theme.fontSmall
    // 文本被选中时显示文本光标，提示「这里可以选」
    cursorVisible: false
    activeFocusOnTab: true
}
