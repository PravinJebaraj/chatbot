frappe.pages['chatbot'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Chatbot',
		single_column: true
	});
};

frappe.pages['chatbot'].on_page_show = function (wrapper) {
	load_chatbot_ui(wrapper);
};

function load_chatbot_ui(wrapper) {
	let $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	frappe.require("chatbot_index.bundle.jsx").then(() => {
		new chatbot.ui.ChatBotUI({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}