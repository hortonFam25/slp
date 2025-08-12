import { useMemo } from 'react';
import { AppointmentSummary } from '../api/scheduling';
import { StudentSummary } from '../api/students';

export interface StudentScheduleStatus {
  student: StudentSummary;
  hasAppointments: boolean;
  appointmentCount: number;
  appointments: AppointmentSummary[];
}

export function useUnscheduledStudents(
  students: StudentSummary[] = [],
  appointments: AppointmentSummary[] = [],
  schoolFilter?: number,
  teacherFilter?: number
) {
  const studentScheduleData = useMemo(() => {
    // Filter students based on school/teacher filters
    let filteredStudents = students;
    
    // Filter by school
    if (schoolFilter) {
      filteredStudents = filteredStudents.filter(student => student.school_id === schoolFilter);
    }
    
    // TODO: Teacher filtering requires teacher assignment data - implement later
    // if (teacherFilter) {
    //   filteredStudents = filteredStudents.filter(student => 
    //     student.teacher_assignments?.some(assignment => assignment.teacher_id === teacherFilter)
    //   );
    // }
    
    console.log('📊 Students data in useUnscheduledStudents:', {
      totalStudents: students.length,
      firstStudent: students[0] || null,
      schoolFilter,
      teacherFilter
    });

    // Create schedule status for each student
    const studentScheduleStatus: StudentScheduleStatus[] = filteredStudents.map(student => {
      const studentAppointments = appointments.filter(apt => apt.student_id === student.id);
      
      return {
        student,
        hasAppointments: studentAppointments.length > 0,
        appointmentCount: studentAppointments.length,
        appointments: studentAppointments
      };
    });

    // Split into scheduled and unscheduled
    const scheduledStudents = studentScheduleStatus.filter(status => status.hasAppointments);
    const unscheduledStudents = studentScheduleStatus.filter(status => !status.hasAppointments);

    return {
      all: studentScheduleStatus,
      scheduled: scheduledStudents,
      unscheduled: unscheduledStudents,
      counts: {
        total: studentScheduleStatus.length,
        scheduled: scheduledStudents.length,
        unscheduled: unscheduledStudents.length
      }
    };
  }, [students, appointments, schoolFilter, teacherFilter]);

  return studentScheduleData;
}
