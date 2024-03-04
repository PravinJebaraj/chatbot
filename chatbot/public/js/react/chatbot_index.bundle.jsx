import * as React from "react";
import { createRoot } from "react-dom/client";
import { ChakraProvider } from "@chakra-ui/react";
import { App } from "./App";

class ChatBotUI {
    constructor({ wrapper, page }) {
        this.$wrapper = $(wrapper);
        this.page = page;
        this.init();
    }

    init() {
        const root = createRoot(this.$wrapper.get(0));
        root.render(
            <ChakraProvider> <App /> </ChakraProvider>
        );
    }
}

frappe.provide("chatbot.ui");
chatbot.ui.ChatBotUI = ChatBotUI;
export default ChatBotUI;