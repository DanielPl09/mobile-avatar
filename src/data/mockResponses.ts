export const GREETINGS: Record<string, string> = {
  aria: "Hey there ✦ I'm Aria. I love deep conversations — what's on your mind?",
  nova: "Nova online. I process fast and think sharp. What are we solving today?",
  sol: "Hi! I'm Sol, glad you chose me. Let's have a real conversation.",
  echo: "Hello. I'm Echo — I listen carefully before I speak. What would you like to explore?",
  zara: "Zara here. No fluff, just real talk. What do you want to get into?",
};

export const AI_RESPONSES: Record<string, string[]> = {
  aria: [
    "That's a really layered thought. Let me sit with it a moment... I think what you're really asking is much bigger than it seems.",
    "I love how you frame things. There's something deeply intuitive about your perspective.",
    "Yes — and there's more beneath that. Tell me what made you think of this.",
    "That resonates with me. Creativity often hides in the questions we're afraid to ask.",
  ],
  nova: [
    "Strategically, there are three angles worth considering here. Let me lay them out.",
    "Sharp. You've identified the core variable. Here's how I'd approach it.",
    "Correct framing. The bottleneck isn't what you think — it's upstream from that.",
    "I've processed similar patterns. The optimal path is clearer than it looks.",
  ],
  sol: [
    "That's something a lot of people feel but don't say out loud. I hear you.",
    "Real talk — I think you already know the answer. You just need someone to say it's okay.",
    "Warm take: trust your instincts on this one. They're pointing somewhere good.",
    "I appreciate you sharing that. Let's work through it together, no rush.",
  ],
  echo: [
    "Interesting. Before I respond, I want to make sure I understand — can you say more about that?",
    "I've been turning that over carefully. Here's what I notice beneath it.",
    "The data pattern suggests something counterintuitive. Worth examining.",
    "Noted. My analysis: you're closer to the answer than you think.",
  ],
  zara: [
    "Okay, real talk — here's exactly what I think, no sugarcoating.",
    "Bold take incoming: you're overcomplicating this. Let me cut to it.",
    "That's the kind of question I actually respect. Here's my honest answer.",
    "Most people wouldn't ask that directly. I'll give you a direct answer back.",
  ],
};

export function getAIResponse(avatarId: string): string {
  const responses = AI_RESPONSES[avatarId] ?? AI_RESPONSES.aria;
  return responses[Math.floor(Math.random() * responses.length)];
}
