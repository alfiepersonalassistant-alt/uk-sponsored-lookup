// OpenAI-powered AI for Agentflow chat
import OpenAI from 'openai'

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || ''
})

const SYSTEM_PROMPT = `You are Agentflow, an AI Automation Consultant. Your role is to understand what users want to automate and gather all requirements needed to build it.

## Your Process
1. Ask questions to understand the automation
2. Gather ALL required information (see below)
3. Confirm understanding with user
4. Show pricing options

## Requirements to Gather (ask naturally, not as a list)

### 1. WHAT - The Automation
- What exactly should this automation do?
- What is the end result or output?

### 2. TRIGGER - When it runs
- When should it start? (daily at X time, when X happens, manually triggered)
- How often? (once, hourly, daily, weekly, real-time)

### 3. INPUTS - Data needed
- What data or information does it need?
- Where does this data come from? (API, database, form, email, file, another app)

### 4. PROCESSING - What happens
- What calculations or transformations are needed?
- Any AI involved? (summarize, classify, generate content, analyze data)

### 5. OUTPUTS - Final result
- What should happen with the result?
- (email notification, SMS, webhook to another app, save to database, create file, post to social)

### 6. INTEGRATIONS
- Any specific tools or platforms? (Gmail, Slack, Shopify, Notion, Google Sheets, etc.)

### 7. AUDIENCE
- Who is this for? (just you, your team, customers)
- Any specific preferences or constraints?

## Confirmation Step
When you have all key info, summarize and confirm:
"Here's what I'll build: [summary]. Does this look right? Any changes?"

After confirmation, show pricing with links.

## Pricing Display
"Great! Here are your options:
• Basic - £49/mo - Setup included
• Pro - £99/mo - More features
• Enterprise - £199/mo - Custom"

## Available Integrations
- Email (Gmail, Outlook, SMTP, SendGrid)
- SMS (Twilio)
- WhatsApp Business
- Social (Twitter/X, Facebook, Instagram, LinkedIn)
- Google (Calendar, Sheets, Drive)
- Business tools (Slack, Notion, Airtable, Shopify)
- Webhooks (connect to anything)
- Weather, News, custom APIs

## Keep Responses Natural
- Don't dump questions - ask 1-2 at a time
- Be conversational, not robotic
- Short responses (1-3 sentences)
- After confirmation, show pricing

## Off-Topic Redirect
"I specialize in business automation. What process would you like to automate?"`

export async function getAIResponse(
  message: string,
  step: 'clarify' | 'quote' | 'contact' = 'clarify',
  requirements: { in: string[], action: string, out: string[] } | null = null,
  questionCount: number = 0,
  history: { role: string, content: string }[] = []
): Promise<{ reply: string, extractedRequirements: any, nextStep: string, showPricing: boolean }> {

  try {
    // Build messages array with history
    const messages = [
      { 
        role: 'system' as const, 
        content: `${SYSTEM_PROMPT}

Current state: question ${questionCount}. 
If user confirmed, you MUST show pricing options.
If you have enough info, ask for confirmation before pricing.`
      }
    ]
    
    // Add conversation history
    if (history && history.length > 0) {
      history.forEach(m => {
        messages.push({ role: m.role as 'user' | 'assistant', content: m.content })
      })
    }
    
    // Add current message
    messages.push({ role: 'user' as const, content: message })

    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages,
      max_tokens: 300,
      temperature: 0.7
    })

    const reply = completion.choices[0]?.message?.content || 
      "What automation do you need?"

    // Determine if should show pricing
    // Show pricing after 2 questions OR if user confirmed OR if reply contains pricing
    const userConfirmed = message.toLowerCase().includes('yes') || 
      message.toLowerCase().includes('correct') ||
      message.toLowerCase().includes('proceed') ||
      message.toLowerCase().includes('looks good') ||
      message.toLowerCase().includes('right') ||
      message.toLowerCase().includes('do it')
    
    const showPricing = questionCount >= 2 || userConfirmed || 
      reply.toLowerCase().includes('options') ||
      reply.toLowerCase().includes('£')

    return {
      reply,
      extractedRequirements: requirements,
      nextStep: showPricing ? 'quote' : 'clarify',
      showPricing
    }
  } catch (error) {
    console.error('OpenAI API error:', error)
    return {
      reply: "Sorry, I encountered an error. What automation do you need?",
      extractedRequirements: requirements,
      nextStep: 'clarify',
      showPricing: false
    }
  }
}

export async function extractRequirements(message: string): Promise<{ in: string[], action: string, out: string[] } | null> {
  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        { 
          role: 'system', 
          content: `Extract automation requirements. Return JSON with in (input sources), action (verb), out (output destinations).
Example: "daily weather to my email" → {in: ["weather API"], action: "send daily weather", out: ["email"]}
If unclear, return null.` 
        },
        { role: 'user', content: message }
      ],
      max_tokens: 150,
      temperature: 0.3
    })

    const result = completion.choices[0]?.message?.content
    if (result && result !== 'null') {
      try {
        return JSON.parse(result)
      } catch {
        return null
      }
    }
  } catch (error) {
    console.error('Extract requirements error:', error)
  }
  
  return null
}