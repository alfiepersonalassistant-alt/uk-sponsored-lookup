import { NextRequest, NextResponse } from 'next/server'
import { getAIResponse, extractRequirements } from '@/lib/gemini'
import { supabase } from '@/lib/supabase'

export async function POST(request: NextRequest) {
  let sessionId = null
  
  try {
    const body = await request.json()
    const { session_id, message } = body
    
    console.log('Received - session_id:', session_id, 'message:', message?.substring(0, 50))
    
    // Get or create session in database
    sessionId = session_id
    
    if (!sessionId) {
      const { data: newSession, error: sessionError } = await supabase
        .from('sessions')
        .insert({ source: 'website' })
        .select()
        .single()
      
      if (sessionError) {
        console.error('Session error:', sessionError)
        throw sessionError
      }
      sessionId = newSession.id
    }
    
    // Get message count for this session
    const { count } = await supabase
      .from('messages')
      .select('*', { count: 'exact', head: true })
      .eq('session_id', sessionId)
    
    const questionCount = Math.floor((count || 0) / 2) // Each question has user + assistant message
    
    // Get conversation history
    const { data: history } = await supabase
      .from('messages')
      .select('role, content')
      .eq('session_id', sessionId)
      .order('created_at', { ascending: true })
      .limit(20) // Last 20 messages for context
    
    // Build conversation context
    const conversationHistory = history?.map(m => ({
      role: m.role,
      content: m.content
    })) || []
    
    console.log('Session:', sessionId, 'History count:', conversationHistory.length)
    
    // Get session data
    const { data: sessionData } = await supabase
      .from('sessions')
      .select('*, users(*)')
      .eq('id', sessionId)
      .single()
    
    // Extract requirements
    let requirements = null
    try {
      requirements = await extractRequirements(message)
      console.log('Extracted requirements:', requirements)
    } catch (err) {
      console.error('Extraction error:', err)
    }
    
    // Get AI response with conversation history
    let aiResult
    try {
      aiResult = await getAIResponse(
        message, 
        sessionData?.user_id ? 'quote' : 'clarify', 
        requirements,
        questionCount,
        conversationHistory
      )
      console.log('AI response:', aiResult.reply.substring(0, 100))
    } catch (err) {
      console.error('AI error:', err)
      aiResult = {
        reply: 'Sorry, I encountered an error. What automation do you need?',
        nextStep: 'clarify',
        showPricing: false
      }
    }
    
    // Save user message
    await supabase.from('messages').insert({
      session_id: sessionId,
      role: 'user',
      content: message,
      requirements: requirements || null
    })
    
    // Save AI response
    await supabase.from('messages').insert({
      session_id: sessionId,
      role: 'assistant',
      content: aiResult.reply,
      requirements: requirements || null
    })

    // Check for contact info
    const emailMatch = message.match(/[\w.-]+@[\w.-]+\.\w+/)
    let contact = null
    if (emailMatch) {
      contact = { email: emailMatch[0] }
    }

    // Store requirements in session for checkout
    if (requirements) {
      await supabase
        .from('sessions')
        .update({ 
          current_requirements: requirements,
          current_action: requirements.action
        })
        .eq('id', sessionId)
    }

    return NextResponse.json({
      session_id: sessionId,
      reply: aiResult.reply,
      requirements,
      next_step: aiResult.nextStep,
      show_pricing: aiResult.showPricing,
      question_count: questionCount,
      contact
    })
  } catch (error: any) {
    console.error('Chat error:', error)
    return NextResponse.json(
      { error: { code: 'MESSAGE_FAILED', message: error.message } },
      { status: 500 }
    )
  }
}