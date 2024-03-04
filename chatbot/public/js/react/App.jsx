import * as React from "react";
import{nanoid} from 'nanoid';

import ChatbotView from "./frontend/chatbot_ui";

export function App(){
    return <ChatbotView sessionID = {nanoid()} />;
}